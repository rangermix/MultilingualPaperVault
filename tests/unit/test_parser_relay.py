"""Model runner relay tests with an in-process upstream transport."""

import gzip
import json

import httpx
import pytest
from starlette.testclient import TestClient

from packages.local_models.catalog import artifact
from packages.parsers.catalog import vlm_lock
from packages.parsers import relay
from packages.parsers.relay import create_app


MODEL_ID = artifact(vlm_lock()['models'][0])['id']
COMPLETIONS = '/engines/vllm/v1/chat/completions'
PNG = ('data:image/png;base64,'
       'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2uoAAAAASUVORK5CYII=')


class Chunks(httpx.AsyncByteStream):
    def __init__(self, *chunks):
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


def completion(*, stream=False):
    return {
        'model': MODEL_ID,
        'messages': [{'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': PNG}},
            {'type': 'text', 'text': 'Read this example page.'},
        ]}],
        'temperature': 0,
        'max_tokens': 8192,
        'stream': stream,
    }


def fail_upstream(request):
    pytest.fail('The request must be handled without contacting Docker Model Runner')


def test_read_routes_use_configured_destinations_and_ignore_client_headers():
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, headers={'Content-Type': 'application/json',
                                            'Set-Cookie': 'upstream=value'},
                              stream=Chunks(b'{}'))

    app = create_app(dmr='http://dmr.example.test:12434',
                     resource_monitor='https://telemetry.example.test/metrics?scope=parser',
                     transport=httpx.MockTransport(respond))
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        assert not calls
        headers = {'Host': 'parser-dmr:12435', 'Authorization': 'Bearer synthetic',
                   'Cookie': 'example=value', 'X-Forwarded-Host': 'forward.example.test'}
        response = client.get('/engines/status', headers=headers)
        assert response.json() == {}
        assert 'set-cookie' not in response.headers
        assert client.get(f'/models/{MODEL_ID}').json() == {}
        assert client.get('/engines/_configure', params={'model': MODEL_ID}).json() == {}
        assert client.get('/capabilities').json() == {}
        assert client.get('/resources').json() == {}

    assert [(request.method, request.url.host, request.url.port, request.url.path)
            for request in calls] == [
        ('GET', 'dmr.example.test', 12434, '/engines/status'),
        ('GET', 'dmr.example.test', 12434, f'/models/{MODEL_ID}'),
        ('GET', 'dmr.example.test', 12434, '/engines/_configure'),
        ('GET', 'dmr.example.test', 12435, '/capabilities'),
        ('GET', 'telemetry.example.test', None, '/metrics'),
    ]
    assert dict(calls[2].url.params) == {'model': MODEL_ID}
    assert dict(calls[4].url.params) == {'scope': 'parser'}
    assert calls[0].headers['host'] == 'dmr.example.test:12434'
    assert {'authorization', 'cookie', 'x-forwarded-host'}.isdisjoint(calls[0].headers)
    assert 'cookie' not in calls[1].headers


@pytest.mark.parametrize(('method', 'path', 'params'), [
    ('GET', '/unexpected', {}),
    ('POST', '/engines/_configure', {}),
    ('GET', '/models/unlisted-model', {}),
    ('GET', '/engines/status', {'debug': 'true'}),
    ('GET', '/engines/_configure', {'model': 'unlisted-model'}),
    ('GET', '/engines/_configure', [('model', MODEL_ID), ('model', MODEL_ID)]),
])
def test_unsupported_method_path_and_query_are_rejected_locally(method, path, params):
    with TestClient(create_app(transport=httpx.MockTransport(fail_upstream))) as client:
        response = client.request(method, path, params=params)
    assert 400 <= response.status_code < 500


@pytest.mark.parametrize(('stream_requested', 'status', 'media_type', 'body', 'compressed'), [
    (False, 200, 'application/json', b'{"id":"example"}', True),
    (True, 200, 'text/event-stream', b'data: {"id":"example"}\n\ndata: [DONE]\n\n', False),
    (False, 503, 'application/json', b'{"error":"example unavailable"}', False),
])
def test_completion_preserves_payload_and_upstream_stream(
    stream_requested, status, media_type, body, compressed,
):
    payload = completion(stream=stream_requested)
    if not stream_requested:
        payload['chat_template_kwargs'] = {'enable_thinking': False}
    wire_body = gzip.compress(body) if compressed else body
    stream = Chunks(wire_body[:8], wire_body[8:])

    async def respond(request):
        assert request.method == 'POST'
        assert request.url.path == COMPLETIONS
        assert json.loads(await request.aread()) == payload
        headers = {'Content-Type': media_type}
        if compressed:
            headers['Content-Encoding'] = 'gzip'
        return httpx.Response(status, headers=headers, stream=stream)

    with TestClient(create_app(transport=httpx.MockTransport(respond))) as client:
        response = client.post(COMPLETIONS, json=payload)
    assert response.status_code == status
    assert response.headers['content-type'].split(';')[0] == media_type
    if compressed:
        assert response.headers['content-encoding'] == 'gzip'
    assert response.content == body
    assert stream.closed


def test_completion_refuses_unlisted_model_remote_image_and_unexpected_fields():
    with TestClient(create_app(transport=httpx.MockTransport(fail_upstream))) as client:
        for data in (
            {**completion(), 'model': 'unlisted-model'},
            {**completion(), 'debug': True},
        ):
            assert 400 <= client.post(COMPLETIONS, json=data).status_code < 500
        remote_image = completion()
        remote_image['messages'][0]['content'][0]['image_url']['url'] = 'https://example.invalid/page.png'
        assert 400 <= client.post(COMPLETIONS, json=remote_image).status_code < 500

        duplicate = json.dumps(completion())[:-1] + ', "stream": true}'
        response = client.post(COMPLETIONS, content=duplicate,
                               headers={'Content-Type': 'application/json'})
        assert 400 <= response.status_code < 500


def test_upload_exceeding_parser_limit_is_rejected_before_upstream(monkeypatch):
    monkeypatch.setattr(relay, 'MAX_COMPLETION_BYTES', 64)
    content = json.dumps(completion()).encode()
    with TestClient(create_app(transport=httpx.MockTransport(fail_upstream))) as client:
        response = client.post(COMPLETIONS, content=iter((content[:32], content[32:])),
                               headers={'Content-Type': 'application/json'})
    assert response.status_code == 413


def test_redirect_does_not_trigger_another_request_or_escape_the_relay():
    calls = []
    stream = Chunks(b'')

    def respond(request):
        calls.append(request)
        return httpx.Response(302, headers={'Location': 'http://elsewhere.example.test/'},
                              stream=stream)

    with TestClient(create_app(transport=httpx.MockTransport(respond))) as client:
        response = client.get('/engines/status')
    assert response.status_code == 502
    assert 'location' not in response.headers
    assert len(calls) == 1
    assert stream.closed
