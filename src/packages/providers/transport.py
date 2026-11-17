"""Bounded HTTP attempts behind the synchronous provider interface."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import math
import time
import zlib

import httpx

from .contract import ProviderFailure

MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def post_response(endpoint, body, headers, *, transport=None, timeout=180):
    """Bound response memory and total elapsed time, including a slow stream.

    HTTPX read timeouts apply to individual reads, so the async cancellation
    deadline also covers headers and continuously arriving response chunks.
    Callers retain their existing classification of connection/status failures.
    """
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ProviderFailure('PROVIDER_CONFIG', 'not_sent')
    def execute():
        return asyncio.run(_post_response(endpoint, body, headers, transport, timeout))
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return execute()
    # This remains a synchronous API when called by an event-loop owner. The
    # request itself has cancellable async I/O; join its thread before returning.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(execute).result()


class _AsyncStream(httpx.AsyncByteStream):
    """Keep existing synchronous injected transports usable by contract tests."""
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        for chunk in self.stream:
            yield chunk
            await asyncio.sleep(0)

    async def aclose(self):
        self.stream.close()


class _InjectedTransport(httpx.AsyncBaseTransport):
    def __init__(self, transport):
        self.transport = transport

    async def handle_async_request(self, request):
        if isinstance(self.transport, httpx.AsyncBaseTransport):
            response = await self.transport.handle_async_request(request)
        else:
            response = self.transport.handle_request(request)
        if not isinstance(response.stream, httpx.AsyncByteStream):
            response.stream = _AsyncStream(response.stream)
        return response

    async def aclose(self):
        if isinstance(self.transport, httpx.AsyncBaseTransport):
            await self.transport.aclose()
        else:
            self.transport.close()


class _Body:
    """Apply the same byte ceiling before and after gzip/deflate expansion."""
    def __init__(self, encoding):
        if encoding not in ('', 'identity', 'gzip', 'deflate'):
            raise ProviderFailure('OUTCOME_UNKNOWN', 'unknown')
        self.encoding = encoding
        self.decoder = (zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == 'gzip'
            else zlib.decompressobj() if encoding == 'deflate' else None)
        # Keep the bounded wire prefix until wrapped deflate is known valid.
        # Raw deflate can begin with a valid-looking zlib header, so a two-byte
        # guess cannot safely replace HTTPX's wrapped/raw fallback.
        self.deflate_prefix = bytearray() if encoding == 'deflate' else None
        self.content = bytearray()
        self.wire_bytes = 0

    def _decode(self, chunk):
        decoded = self.decoder.decompress(chunk, MAX_RESPONSE_BYTES - len(self.content) + 1) if self.decoder else chunk
        if len(self.content) + len(decoded) > MAX_RESPONSE_BYTES:
            raise OverflowError
        self.content.extend(decoded)

    def _raw_deflate(self):
        prefix = bytes(self.deflate_prefix)
        self.deflate_prefix = None
        self.decoder = zlib.decompressobj(-zlib.MAX_WBITS)
        self.content.clear()
        self._decode(prefix)

    def feed(self, chunk):
        self.wire_bytes += len(chunk)
        if self.wire_bytes > MAX_RESPONSE_BYTES:
            raise ProviderFailure('OUTCOME_UNKNOWN', 'unknown')
        if self.deflate_prefix is not None:
            self.deflate_prefix.extend(chunk)
        try:
            try:
                self._decode(chunk)
            except (zlib.error, OverflowError):
                if self.deflate_prefix is None:
                    raise
                self._raw_deflate()
        except (zlib.error, OverflowError):
            raise ProviderFailure('OUTCOME_UNKNOWN', 'unknown') from None

    def finish(self):
        if self.deflate_prefix is not None and not self.decoder.eof:
            try:
                self._raw_deflate()
            except (zlib.error, OverflowError):
                raise ProviderFailure('OUTCOME_UNKNOWN', 'unknown') from None
        if self.encoding in ('gzip', 'deflate') and (self.decoder is None or not self.decoder.eof):
            raise ProviderFailure('OUTCOME_UNKNOWN', 'unknown')
        return bytes(self.content)


async def _post_response(endpoint, body, headers, transport, timeout):
    deadline = time.monotonic() + timeout

    def check_deadline():
        if time.monotonic() >= deadline:
            raise ProviderFailure('OUTCOME_UNKNOWN', 'unknown')

    try:
        async with asyncio.timeout(timeout):
            async with httpx.AsyncClient(
                    transport=_InjectedTransport(transport) if transport is not None else httpx.AsyncHTTPTransport(retries=0),
                    timeout=httpx.Timeout(timeout, connect=min(15, timeout)),
                    follow_redirects=False, trust_env=False) as client:
                async with client.stream('POST', endpoint, json=body,
                        headers=headers) as response:
                    check_deadline()
                    content = b''
                    if response.status_code == 200:
                        encoding = response.headers.get('content-encoding', 'identity').strip().lower()
                        length = response.headers.get('content-length')
                        if length is not None:
                            try:
                                declared = int(length)
                            except ValueError:
                                raise ProviderFailure('OUTCOME_UNKNOWN', 'unknown') from None
                            if not 0 <= declared <= MAX_RESPONSE_BYTES:
                                raise ProviderFailure('OUTCOME_UNKNOWN', 'unknown')
                        # Preloaded injected responses have already been decoded
                        # by HTTPX; live streams are read raw and decoded bounded.
                        reader = _Body('identity' if response.is_stream_consumed else encoding)
                        if response.is_stream_consumed:
                            reader.feed(response.content)
                        else:
                            async for chunk in response.aiter_raw():
                                check_deadline()
                                reader.feed(chunk)
                        content = reader.finish()
                        check_deadline()
                    # Error classification needs only status and headers. Never
                    # consume or retain an arbitrary provider error response.
                    normalized_headers = response.headers.copy()
                    for name in ('content-encoding', 'content-length'):
                        normalized_headers.pop(name, None)
                    return httpx.Response(response.status_code, headers=normalized_headers,
                        content=content, request=response.request)
    except TimeoutError:
        raise ProviderFailure('OUTCOME_UNKNOWN', 'unknown') from None
