"""Untrusted provider responses stay bounded without implying a free retry."""
import asyncio
import gzip
import json
import socket
import threading
import time
import zlib

import httpx
import pytest

from packages.providers import transport
from packages.providers.contract import ProviderFailure
from packages.providers.native import NativeProvider
from packages.providers.openai_responses import OpenAIResponses
from tests.unit.test_claude_messages import response as claude_response
from tests.unit.test_gemini_interactions import response as gemini_response
from tests.unit.test_openai_responses import PROFILE, UNIT

PROTOCOLS = ('responses', 'chat_completions', 'gemini_interactions', 'claude_messages')


def adapter(protocol, wire, *, timeout=2):
    profile = PROFILE | {'api_protocol': protocol, 'auth_mode': 'none',
        'endpoint': 'https://synthetic.invalid/exact',
        'provider': {'gemini_interactions': 'gemini', 'claude_messages': 'anthropic'}.get(protocol, 'openai')}
    if protocol in ('responses', 'chat_completions'):
        instance = OpenAIResponses(transport=httpx.MockTransport(wire), endpoint=profile['endpoint'],
            api_protocol=protocol, auth_mode='none', timeout=timeout)
    else:
        instance = NativeProvider(profile, transport=httpx.MockTransport(wire), timeout=timeout)
    return instance, profile


def envelope(protocol):
    if protocol == 'claude_messages':
        return claude_response(model=PROFILE['model_id'])
    if protocol == 'gemini_interactions':
        return gemini_response(model=PROFILE['model_id'])
    if protocol == 'chat_completions':
        return {'id': 'synthetic', 'model': PROFILE['model_id'],
            'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': '{"results":[]}'}}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 2}}
    return {'id': 'synthetic', 'model': PROFILE['model_id'], 'status': 'completed',
        'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{"results":[]}'}]}],
        'usage': {'input_tokens': 1, 'output_tokens': 2}}


class Chunks(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.consumed = 0
        self.closed = False

    def __iter__(self):
        for chunk in self.chunks:
            self.consumed += 1
            yield chunk

    def close(self):
        self.closed = True


@pytest.mark.parametrize('protocol', PROTOCOLS)
@pytest.mark.parametrize('length', [None, '1'])
def test_stream_cap_stops_consumption_without_retry_or_known_usage(monkeypatch, protocol, length):
    monkeypatch.setattr(transport, 'MAX_RESPONSE_BYTES', 1024)
    chunks = Chunks([b'x' * 600, b'y' * 600, b'must-not-be-consumed'])
    calls = []
    def wire(request):
        calls.append(request)
        return httpx.Response(200, headers={'content-length': length} if length else {}, stream=chunks)
    instance, profile = adapter(protocol, wire)
    with pytest.raises(ProviderFailure) as error:
        instance.translate([UNIT], profile, [])
    assert (error.value.code, error.value.outcome) == ('OUTCOME_UNKNOWN', 'unknown')
    assert len(calls) == 1 and chunks.consumed == 2 and chunks.closed


@pytest.mark.parametrize('protocol', PROTOCOLS)
def test_declared_oversize_rejected_before_reading_any_body(monkeypatch, protocol):
    monkeypatch.setattr(transport, 'MAX_RESPONSE_BYTES', 1024)
    chunks = Chunks([b'must-not-be-consumed'])
    instance, profile = adapter(protocol, lambda request: httpx.Response(200,
        headers={'content-length': '1025'}, stream=chunks))
    with pytest.raises(ProviderFailure) as error:
        instance.translate([UNIT], profile, [])
    assert error.value.outcome == 'unknown' and chunks.consumed == 0 and chunks.closed


@pytest.mark.parametrize('protocol', PROTOCOLS)
@pytest.mark.parametrize('encoding', ['identity', 'gzip', 'deflate', 'raw-deflate', 'ambiguous-raw-deflate'])
def test_valid_streamed_compression_preserves_normalization(protocol, encoding):
    body = json.dumps(envelope(protocol)).encode()
    if encoding == 'gzip':
        body = gzip.compress(body)
    elif encoding == 'deflate':
        body = zlib.compress(body)
    elif encoding == 'raw-deflate':
        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        body = compressor.compress(body) + compressor.flush()
    elif encoding == 'ambiguous-raw-deflate':
        # A raw stored block may start with the same bytes as a zlib header.
        # Its padding is valid; the following final stored block holds JSON.
        body = (b'\x78\x9c\x00\x63\xff' + b' ' * 156 + b'\x01'
            + len(body).to_bytes(2, 'little') + (65535 - len(body)).to_bytes(2, 'little') + body)
    # Fragment headers as well as data to test raw/zlib deflate detection.
    chunks = Chunks([body[index:index + 1] for index in range(len(body))])
    instance, profile = adapter(protocol, lambda request: httpx.Response(200,
        headers={'content-encoding': 'deflate' if encoding in ('raw-deflate', 'ambiguous-raw-deflate') else encoding}, stream=chunks))
    result = instance.translate([UNIT], profile, [])
    assert result['status'] == 'completed' and result['response_model'] == PROFILE['model_id']
    assert result['usage'] and chunks.closed


@pytest.mark.parametrize('protocol', PROTOCOLS)
@pytest.mark.parametrize('encoding', ['gzip', 'deflate', 'raw-deflate'])
def test_compression_expansion_is_bounded_before_allocating_full_output(monkeypatch, protocol, encoding):
    monkeypatch.setattr(transport, 'MAX_RESPONSE_BYTES', 1024)
    if encoding == 'raw-deflate':
        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        encoded = compressor.compress(b'x' * 65536) + compressor.flush()
    else:
        encoded = (gzip.compress if encoding == 'gzip' else zlib.compress)(b'x' * 65536)
    chunks = Chunks([encoded, b'must-not-be-consumed'])
    instance, profile = adapter(protocol, lambda request: httpx.Response(200,
        headers={'content-encoding': 'deflate' if encoding == 'raw-deflate' else encoding}, stream=chunks))
    with pytest.raises(ProviderFailure) as error:
        instance.translate([UNIT], profile, [])
    assert error.value.outcome == 'unknown' and chunks.consumed == 1 and chunks.closed


@pytest.mark.parametrize('protocol', PROTOCOLS)
def test_absolute_deadline_cancels_blocked_response_and_closes_stream(protocol):
    closed = []
    calls = []
    class Waiting(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b' '
            await asyncio.sleep(30)
            pytest.fail('deadline failed to cancel response')
        async def aclose(self):
            closed.append(True)
    def wire(request):
        calls.append(request)
        return httpx.Response(200, stream=Waiting())
    instance, profile = adapter(protocol, wire, timeout=.05)
    started = time.monotonic()
    with pytest.raises(ProviderFailure) as error:
        instance.translate([UNIT], profile, [])
    elapsed = time.monotonic() - started
    assert error.value.outcome == 'unknown' and len(calls) == 1 and closed == [True]
    assert elapsed < 2  # Broad guard; the simulated provider would wait 30 seconds.


@pytest.mark.parametrize('protocol', PROTOCOLS)
def test_monotonic_deadline_stops_continuously_arriving_chunks(monkeypatch, protocol):
    class Clock:
        value = 0
        def monotonic(self):
            return self.value
    clock = Clock()
    monkeypatch.setattr(transport, 'time', clock)
    class Drip(Chunks):
        def __iter__(self):
            for chunk in super().__iter__():
                clock.value += 1
                yield chunk
    chunks = Drip([b' ', b' ', b' ', b'must-not-be-consumed'])
    instance, profile = adapter(protocol, lambda request: httpx.Response(200, stream=chunks), timeout=2)
    with pytest.raises(ProviderFailure) as error:
        instance.translate([UNIT], profile, [])
    assert error.value.outcome == 'unknown' and chunks.consumed == 2 and chunks.closed


@pytest.mark.parametrize('protocol', PROTOCOLS)
@pytest.mark.parametrize('status,outcome', [(401, 'not_executed'), (429, 'not_executed'), (500, 'unknown')])
def test_status_classification_never_reads_unbounded_error_body(protocol, status, outcome):
    chunks = Chunks([b'must-not-be-consumed'])
    instance, profile = adapter(protocol, lambda request: httpx.Response(status, stream=chunks))
    with pytest.raises(ProviderFailure) as error:
        instance.translate([UNIT], profile, [])
    assert error.value.outcome == outcome and chunks.consumed == 0 and chunks.closed


def test_sync_transport_and_existing_event_loop_remain_supported():
    class SyncTransport(httpx.BaseTransport):
        def handle_request(self, request):
            return httpx.Response(200, stream=Chunks([json.dumps(envelope('responses')).encode()]))
    async def caller():
        provider = OpenAIResponses(transport=SyncTransport(), auth_mode='none')
        return provider.translate([UNIT], PROFILE | {'auth_mode': 'none'}, [])
    assert asyncio.run(caller())['status'] == 'completed'


def test_real_loopback_drip_cannot_extend_deadline_with_regular_network_reads():
    """An actual socket keeps arriving inside each read timeout; total time wins."""
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(2)
    stop = threading.Event()
    sent = []
    def serve():
        try:
            with listener.accept()[0] as connection:
                connection.settimeout(2)
                request = bytearray()
                while b'\r\n\r\n' not in request:
                    request.extend(connection.recv(4096))
                connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 10000\r\n\r\n')
                for _ in range(100):
                    connection.sendall(b' ')
                    sent.append(True)
                    if stop.wait(.02):
                        break
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            listener.close()
    thread = threading.Thread(target=serve)
    thread.start()
    profile = PROFILE | {'endpoint': f'http://127.0.0.1:{listener.getsockname()[1]}/synthetic', 'auth_mode': 'none'}
    provider = OpenAIResponses(endpoint=profile['endpoint'], auth_mode='none', timeout=.15)
    started = time.monotonic()
    try:
        with pytest.raises(ProviderFailure) as error:
            provider.translate([UNIT], profile, [])
        assert error.value.outcome == 'unknown' and time.monotonic() - started < 1
        assert len(sent) >= 2
    finally:
        stop.set()
        thread.join(3)
    assert not thread.is_alive()
