"""Restricted Docker Model Runner client for the isolated PDF parser."""
import asyncio
from contextlib import asynccontextmanager
import os
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import ClientDisconnect
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from packages.ir import strict_loads
from packages.local_models.catalog import artifact
from .catalog import vlm_lock
from .model_service import runner_url


# The parser renders at most about 16 million RGB pixels with bounded dimensions.
# This leaves headroom above 64 MB of base64 for PNG rows, compression and JSON.
MAX_COMPLETION_BYTES = 64 * 1024 * 1024
CONFIGURE_PATH = '/engines/_configure'
COMPLETION_PATH = '/engines/vllm/v1/chat/completions'
MONITOR_URL = 'http://vllm-runner:12435/resources'


class _RequestModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class _InlineImage(_RequestModel):
    url: str = Field(pattern=r'^data:image/png;base64,')


class _ImagePart(_RequestModel):
    type: Literal['image_url']
    image_url: _InlineImage


class _TextPart(_RequestModel):
    type: Literal['text']
    text: str


class _PageMessage(_RequestModel):
    role: Literal['user']
    content: tuple[_ImagePart, _TextPart]


class _TemplateOptions(_RequestModel):
    enable_thinking: Literal[False]


class _Completion(_RequestModel):
    model: str
    messages: tuple[_PageMessage]
    temperature: Literal[0]
    max_tokens: Literal[8192]
    stream: StrictBool
    chat_template_kwargs: _TemplateOptions | None = None


class _UpstreamResponse(StreamingResponse):
    def __init__(self, upstream):
        self.upstream = upstream
        headers = {name: upstream.headers[name] for name in ('content-type', 'content-encoding')
                   if name in upstream.headers}
        super().__init__(self._chunks(), status_code=upstream.status_code, headers=headers)

    async def _chunks(self):
        try:
            async for chunk in self.upstream.aiter_raw():
                yield chunk
        except httpx.HTTPError:
            # After response headers, terminate the stream with a generic error.
            raise RuntimeError('Model runner response stream failed') from None

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            await self.upstream.aclose()


def _upstream_urls(dmr, resource_monitor):
    try:
        runner = httpx.URL(runner_url(dmr))
    except (httpx.InvalidURL, ValueError):
        raise ValueError('PARSER_MODEL_RUNNER_URL_INVALID') from None
    try:
        monitor = httpx.URL(resource_monitor or os.environ.get('RESOURCE_MONITOR_URL') or MONITOR_URL)
    except httpx.InvalidURL:
        raise ValueError('RESOURCE_MONITOR_URL_INVALID') from None
    if monitor.scheme not in ('http', 'https') or not monitor.host or monitor.userinfo or monitor.fragment:
        raise ValueError('RESOURCE_MONITOR_URL_INVALID')
    return runner, monitor


async def _read_completion(request, pinned_models):
    if request.headers.get('content-type', '').partition(';')[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'Expected application/json')
    body = bytearray()
    try:
        async with asyncio.timeout(300):
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_COMPLETION_BYTES:
                    raise HTTPException(413, 'Completion request exceeds parser limit')
                body.extend(chunk)
            completion = _Completion.model_validate(strict_loads(body))
    except (ClientDisconnect, ValueError, RecursionError):
        raise HTTPException(400, 'Invalid parser completion request') from None
    except TimeoutError:
        raise HTTPException(408, 'Parser completion upload timed out') from None
    if completion.model not in pinned_models:
        raise HTTPException(400, 'Unknown parser model')
    return completion.model_dump(exclude_none=True)


async def _forward(request, target, payload=None):
    # Build from the fixed URL and the validated payload. Do not merge headers
    # or cookies from the caller or the upstream client's cookie jar.
    outgoing = httpx.Request(request.method, target, json=payload,
                             headers={'Accept-Encoding': 'identity'})
    try:
        upstream = await request.app.state.client.send(outgoing, stream=True)
    except httpx.TimeoutException:
        raise HTTPException(504, 'Model runner timed out') from None
    except httpx.HTTPError:
        raise HTTPException(502, 'Model runner unavailable') from None
    if 300 <= upstream.status_code < 400:
        await upstream.aclose()
        raise HTTPException(502, 'Model runner redirects are disabled')
    return _UpstreamResponse(upstream)


def create_app(dmr=None, resource_monitor=None, transport=None):
    runner, monitor = _upstream_urls(dmr, resource_monitor)
    pinned_models = frozenset(artifact(model)['id'] for model in vlm_lock()['models'])
    reads = {
        '/engines/status': runner.copy_with(path='/engines/status'),
        '/capabilities': runner.copy_with(path='/capabilities', port=12435),
        '/resources': monitor,
    }

    @asynccontextmanager
    async def lifespan(app):
        timeout = httpx.Timeout(300, connect=4, pool=4)
        async with httpx.AsyncClient(transport=transport, timeout=timeout,
                                     follow_redirects=False, trust_env=False) as client:
            app.state.client = client
            app.state.completion_slot = asyncio.Semaphore(1)
            yield

    async def health(request):
        return JSONResponse({'status': 'ok'})

    async def read(request):
        if request.method != 'GET':
            raise HTTPException(405, headers={'Allow': 'GET'})
        if request.query_params:
            raise HTTPException(400, 'Unexpected query parameters')
        return await _forward(request, reads[request.scope['path']])

    async def metadata(request):
        if request.method != 'GET':
            raise HTTPException(405, headers={'Allow': 'GET'})
        ident = request.path_params['model_id']
        if request.query_params or ident not in pinned_models:
            raise HTTPException(400, 'Unknown parser model or query')
        return await _forward(request, runner.copy_with(path='/models/' + ident))

    async def configuration(request):
        if request.method != 'GET':
            raise HTTPException(405, headers={'Allow': 'GET'})
        query = request.query_params.multi_items()
        if len(query) != 1 or query[0][0] != 'model' or query[0][1] not in pinned_models:
            raise HTTPException(400, 'Expected one pinned parser model')
        return await _forward(request, runner.copy_with(path=CONFIGURE_PATH, params=query))

    async def completion(request):
        if request.query_params:
            raise HTTPException(400, 'Unexpected query parameters')
        async with request.app.state.completion_slot:
            payload = await _read_completion(request, pinned_models)
            return await _forward(request, runner.copy_with(path=COMPLETION_PATH), payload)

    routes = [Route('/health', health)]
    routes.extend(Route(path, read) for path in reads)
    routes.extend([
        Route('/models/{model_id}', metadata),
        Route(CONFIGURE_PATH, configuration),
        Route(COMPLETION_PATH, completion, methods=['POST']),
    ])
    app = Starlette(routes=routes, lifespan=lifespan)
    app.router.redirect_slashes = False
    return app


app = create_app()
