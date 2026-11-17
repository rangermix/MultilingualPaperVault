"""Offline cache/model identity regressions, with no real weights or inference."""
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
import pytest

from packages.ir import canonical_bytes, strict_loads
from packages.parsers.catalog import download_spec, public_models, vlm_lock
from packages.parsers.download import download
from packages.parsers.inspect import PDFError
from packages.parsers.model_service import Manager, create_app
from packages.parsers.profiles import (DMR_PROFILES, PROFILE_IDS, UNAVAILABLE_PROFILES,
    SURYA_PROFILE, INFINITY_PRO_PROFILE, PROKOPE_PROFILE, OXR_PROFILE)


def spec(data=b'locked', path='weights/model.bin'):
    return {'path': path, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'url': 'https://huggingface.co/test/resolve/fixed/model'}


def test_executable_and_admitted_models_have_pinned_manifests_and_public_choices():
    rows = {r['id']: r for r in public_models()}
    assert set(rows) == set(PROFILE_IDS)
    assert len(vlm_lock()['models']) == 5
    for model in vlm_lock()['models']:
        assert len(model['revision']) == 40
        assert model['files'] and all(len(f['sha256']) == 64 and f['size'] > 0 for f in model['files'])
        assert rows[model['id']]['download_bytes'] == sum(f['size'] for f in model['files'])
        assert rows[model['id']]['model_id'] == model['repo']
        assert model['id'] in download_spec(model['id'])[0]['path'] or model['revision'] in download_spec(model['id'])[0]['path']
    assert rows[INFINITY_PRO_PROFILE]['devices'] == ['dmr']
    assert set(DMR_PROFILES) == set(PROFILE_IDS) - set(UNAVAILABLE_PROFILES)
    assert {model['id'] for model in vlm_lock()['models']} == set(DMR_PROFILES)
    assert rows[PROKOPE_PROFILE]['download_bytes'] is None
    assert rows[PROKOPE_PROFILE]['manifest_id'] is None
    assert rows[PROKOPE_PROFILE]['memory_reference'] is None
    for profile, unavailable in UNAVAILABLE_PROFILES.items():
        assert rows[profile]['availability'] == rows[profile]['status'] == 'unavailable'
        assert rows[profile]['code'] == unavailable['code']
        assert rows[profile]['model_id'] == unavailable['model_id']
        assert rows[profile]['revision'] == unavailable['revision']


def test_health_and_default_listing_never_download_or_contact_runner(tmp_path, monkeypatch):
    monkeypatch.delenv('PARSER_DMR_OXR', raising=False)
    def reject(request):
        pytest.fail('Startup/listing must not contact a model or weight endpoint')
    app = create_app(tmp_path / 'absent', httpx.MockTransport(reject))
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        rows = {row['id']: row for row in client.get('/models').json()['models']}
        assert len(rows) == 6
        assert rows[OXR_PROFILE]['status'] == 'unavailable'
        assert rows[OXR_PROFILE]['code'] == 'PARSER_MODEL_PLUGIN_REQUIRED'
        assert all(row['status'] == ('unavailable' if profile in UNAVAILABLE_PROFILES else 'not_downloaded')
                   for profile, row in rows.items() if profile != OXR_PROFILE)
    assert not (tmp_path / 'absent').exists()


@pytest.mark.parametrize('body', [b'wrong!', b'locked extra', b'short'])
def test_bad_download_never_replaces_files_or_leaves_parts(tmp_path, body):
    old = tmp_path / 'weights/model.bin'
    old.parent.mkdir()
    old.write_bytes(b'previous bytes')
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=body))) as client:
        with pytest.raises(ValueError, match='HASH_MISMATCH'):
            download([spec()], tmp_path, client)
    assert old.read_bytes() == b'previous bytes'
    assert not list(tmp_path.rglob('*.part'))


def test_cache_reuses_verified_files_and_resumes_failed_preparation(tmp_path):
    requests = []
    def fetch(request):
        requests.append(str(request.url))
        return httpx.Response(200, content=b'locked')
    with httpx.Client(transport=httpx.MockTransport(fetch)) as client:
        download([spec()], tmp_path, client)
        download([spec()], tmp_path, client)
    assert len(requests) == 1
    (tmp_path / 'weights/model.bin').write_bytes(b'tamper')
    with httpx.Client(transport=httpx.MockTransport(fetch)) as client:
        download([spec()], tmp_path, client)
    assert len(requests) == 2 and (tmp_path / 'weights/model.bin').read_bytes() == b'locked'


def test_parser_reports_corrupt_cache_as_hash_mismatch(tmp_path, monkeypatch):
    from packages.parsers.preparation import verify_cached_models
    target = tmp_path / 'weights/model.bin'
    target.parent.mkdir()
    target.write_bytes(b'tamper')
    monkeypatch.setattr('packages.parsers.preparation.download_spec', lambda _: [spec()])
    with pytest.raises(PDFError, match='PARSER_MODEL_HASH_MISMATCH'):
        verify_cached_models(SURYA_PROFILE, tmp_path)


@pytest.mark.parametrize(('profile', 'status', 'code'), [
    (SURYA_PROFILE, 'failed', 'PARSER_DMR_BACKEND_UNAVAILABLE'),
    (SURYA_PROFILE, 'failed', 'PARSER_DMR_CONFIGURATION_FAILED'),
    (OXR_PROFILE, 'unavailable', 'PARSER_MODEL_PLUGIN_REQUIRED'),
])
def test_parser_preserves_preparation_failure_code(tmp_path, monkeypatch, profile, status, code):
    from types import SimpleNamespace
    from packages.parsers.preparation import prepare_models
    monkeypatch.setenv('PARSER_DMR_OXR', '1')
    monkeypatch.setattr('packages.parsers.preparation.time', SimpleNamespace(
        sleep=lambda _: pytest.fail('Preparation has reached a terminal state')))
    def fetch(request):
        return httpx.Response(202 if request.method == 'POST' else 200,
                             json={'status': status, 'code': code})
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(fetch), **kwargs))
    with pytest.raises(PDFError, match=code):
        prepare_models(profile, tmp_path, SimpleNamespace(device='dmr', backend='vllm'))


@pytest.mark.parametrize(('profile', 'backend', 'vram_samples'), [
    (profile, backend, (24 * 1024 ** 3,) if backend == 'vllm' else ())
    for profile in DMR_PROFILES if profile != OXR_PROFILE for backend in ('vllm', 'mlx')
] + [(OXR_PROFILE, 'vllm', (None, 24 * 1024 ** 3)),
     (OXR_PROFILE, 'vllm', (None, None, None))])
def test_dmr_preparation_uses_allowed_engine_flags_and_exact_import(tmp_path, monkeypatch, profile, backend, vram_samples):
    import time
    from types import SimpleNamespace
    from packages.parsers.catalog import vlm_model
    from packages.local_models.catalog import artifact
    model = vlm_model(profile)
    ident = artifact(model)['id']
    samples = iter(vram_samples)
    observed = []
    retry_delays = []

    def capacity():
        total = next(samples)
        observed.append(total)
        return {'vram_total_bytes': total}

    monkeypatch.setattr('packages.resources.telemetry.capacity', capacity)
    if profile == OXR_PROFILE:
        monkeypatch.setenv('PARSER_DMR_OXR', '1')
        monkeypatch.setattr('packages.parsers.model_service.time', SimpleNamespace(
            monotonic=time.monotonic, sleep=retry_delays.append))
    installed = False
    calls = []
    # Replay the real DMR flag rejection; this previously blocked every vLLM
    # parser after a successful download/import, before any page inference.
    allowed_flags = {'--gpu-memory-utilization', '--max-num-seqs', '--max-num-batched-tokens'}
    def fetch(request):
        nonlocal installed
        calls.append((request.method, request.url.path))
        if request.url.path == '/engines/status':
            return httpx.Response(200, json={'vllm': 'Running: vllm-metal test' if backend == 'mlx' else 'Running: vllm test'})
        if request.url.path == '/capabilities':
            assert profile == OXR_PROFILE
            assert str(request.url) == 'http://runner:12435/capabilities'
            requirements = model['runtime_requirements']
            return httpx.Response(200, json={'oxr': {
                'model_artifact_id': ident, 'vllm_version': requirements['vllm_version'],
                'plugin_revision': requirements['plugin_revision'],
            }})
        if request.url.path == '/models/' + ident:
            return httpx.Response(200, json={'id': ident, 'config': {'format': 'safetensors'}}) if installed else httpx.Response(404)
        if request.url.path == '/models/load':
            assert request.content == b'synthetic pinned archive'
            installed = True
            return httpx.Response(200)
        if request.url.path == '/engines/_configure':
            assert request.url.params['model'] == ident
            return httpx.Response(200, json=[])
        if request.url.path == '/engines/vllm/_configure':
            body = strict_loads(request.content)
            assert body['model'] == ident
            assert body['context-size'] == model['context_size']
            assert body['keep_alive'] == '30s'
            flags = body['runtime-flags']
            if backend == 'mlx':
                assert flags == []
            if profile == OXR_PROFILE:
                assert flags[:2] == ['--gpu-memory-utilization', '0.411']
            if any(flag.startswith('--') and flag not in allowed_flags for flag in flags):
                return httpx.Response(500, text='runtime flag is not allowed for backend vllm')
            return httpx.Response(200)
        pytest.fail('Preparation must not request inference or contact another model: ' + str(request.url))
    def record_download(*args):
        calls.append(('download', None))
    monkeypatch.setattr('packages.parsers.model_service.download', record_download)
    monkeypatch.setattr('packages.local_models.download.archive', lambda *args: iter([b'synthetic pinned archive']))
    manager = Manager(tmp_path, httpx.MockTransport(fetch), dmr='http://runner')
    manager.states[(profile, backend)] = {'status': 'downloading'}
    manager._prepare(profile, backend)
    assert observed == list(vram_samples)
    if profile == OXR_PROFILE:
        assert retry_delays == [2] * (len(vram_samples) - 1)
        if vram_samples[-1] is None:
            assert manager.state(profile, backend) == {
                'status': 'failed', 'code': 'PARSER_DMR_CONFIGURATION_FAILED'}
            assert not manager.receipt(profile, backend).exists()
            assert ('POST', '/engines/vllm/_configure') not in calls
            return
    assert manager.state(profile, backend)['status'] == 'ready'
    assert manager.receipt(profile, backend).is_file()
    capability = [('GET', '/capabilities')] if profile == OXR_PROFILE else []
    assert calls == [('GET', '/engines/status'), *capability, ('download', None),
                     ('GET', '/engines/status'), *capability, ('GET', '/models/' + ident),
                     ('POST', '/models/load'), ('GET', '/models/' + ident),
                     ('GET', '/engines/_configure'), ('POST', '/engines/vllm/_configure'), *capability]


@pytest.mark.parametrize('backend', ['vllm', 'mlx'])
@pytest.mark.parametrize('changed', [None, 'model', 'backend', 'mode', 'context', 'flags', 'keep_alive'])
def test_preparation_reuses_only_exact_existing_configuration(tmp_path, monkeypatch, backend, changed):
    from packages.parsers.catalog import vlm_model
    from packages.parsers.model_service import dmr_flags
    from packages.local_models.catalog import artifact
    model = vlm_model(SURYA_PROFILE)
    ident = artifact(model)['id']
    config = {'context-size': model['context_size'], 'keep_alive': '30s',
              'runtime-flags': dmr_flags(model, backend) or None}
    row = {'Backend': 'vllm', 'ModelID': ident, 'Mode': 'completion', 'Config': config}
    if changed == 'model':
        row['ModelID'] = 'sha256:' + '0' * 64
    elif changed == 'backend':
        row['Backend'] = 'llama.cpp'
    elif changed == 'mode':
        row['Mode'] = 'embedding'
    elif changed == 'context':
        config['context-size'] = 4096
    elif changed == 'flags':
        config['runtime-flags'] = ['--max-num-seqs', '4']
    elif changed == 'keep_alive':
        config['keep_alive'] = '5m'
    events = []
    def fetch(request):
        if request.url.path == '/engines/status':
            return httpx.Response(200, json={'vllm': 'Running: vllm-metal test' if backend == 'mlx' else 'Running: vllm test'})
        if request.url.path == '/models/' + ident:
            return httpx.Response(200, json={'id': ident, 'config': {'format': 'safetensors'}})
        if request.url.path == '/engines/_configure':
            assert request.url.params['model'] == ident
            events.append('configuration_checked')
            return httpx.Response(200, json=[row])
        assert request.method == 'POST' and request.url.path == '/engines/vllm/_configure'
        assert strict_loads(request.content) == {'model': ident, 'context-size': model['context_size'],
                                                'keep_alive': '30s', 'runtime-flags': dmr_flags(model, backend)}
        events.append('configuration_posted')
        return httpx.Response(200)
    monkeypatch.setattr('packages.parsers.model_service.download', lambda *args: events.append('hashes_rechecked'))
    manager = Manager(tmp_path, httpx.MockTransport(fetch), dmr='http://runner')
    manager.states[(SURYA_PROFILE, backend)] = {'status': 'downloading'}
    manager._prepare(SURYA_PROFILE, backend)
    assert manager.state(SURYA_PROFILE, backend)['status'] == 'ready'
    assert events == ['hashes_rechecked', 'configuration_checked'] + (['configuration_posted'] if changed else [])


def test_rejected_dmr_configuration_has_safe_failure_code_and_no_receipt(tmp_path, monkeypatch):
    from packages.parsers.catalog import vlm_model
    from packages.local_models.catalog import artifact
    ident = artifact(vlm_model(SURYA_PROFILE))['id']
    def fetch(request):
        if request.url.path == '/engines/status':
            return httpx.Response(200, json={'vllm': 'Running: vllm test'})
        if request.url.path == '/models/' + ident:
            return httpx.Response(200, json={'id': ident, 'config': {'format': 'safetensors'}})
        if request.url.path == '/engines/_configure':
            return httpx.Response(200, json=[])
        assert request.url.path == '/engines/vllm/_configure'
        return httpx.Response(500, text='untrusted backend detail containing private credentials')
    monkeypatch.setattr('packages.parsers.model_service.download', lambda *args: None)
    manager = Manager(tmp_path, httpx.MockTransport(fetch), dmr='http://runner')
    manager.states[(SURYA_PROFILE, 'vllm')] = {'status': 'downloading'}
    manager._prepare(SURYA_PROFILE, 'vllm')
    assert manager.state(SURYA_PROFILE) == {'status': 'failed', 'code': 'PARSER_DMR_CONFIGURATION_FAILED'}
    assert not manager.receipt(SURYA_PROFILE, 'vllm').exists()


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'bad\\path', 'link/file'])
def test_unsafe_cache_paths_fail_before_network(tmp_path, path):
    outside = tmp_path.parent / (tmp_path.name + '-outside')
    outside.mkdir(exist_ok=True)
    (tmp_path / 'link').symlink_to(outside, target_is_directory=True)
    with httpx.Client(transport=httpx.MockTransport(lambda req: pytest.fail('No unsafe download'))) as client:
        with pytest.raises(ValueError):
            download([spec(path=path)], tmp_path, client)
    assert not list(outside.iterdir())


def test_manager_commits_receipt_only_after_verified_download(tmp_path, monkeypatch):
    monkeypatch.setattr('packages.parsers.model_service.download_spec', lambda _: [spec()])
    manager = Manager(tmp_path, httpx.MockTransport(lambda req: httpx.Response(200, json={'vllm': 'Running: vllm test'}) if req.url.path == '/engines/status' else httpx.Response(200, content=b'locked')))
    monkeypatch.setattr(manager, 'prepare_dmr', lambda *args: None)
    manager.states[(SURYA_PROFILE, 'vllm')] = {'status': 'downloading'}
    manager._prepare(SURYA_PROFILE, 'vllm')
    assert manager.state(SURYA_PROFILE)['status'] == 'ready'
    assert strict_loads(manager.receipt(SURYA_PROFILE, 'vllm').read_bytes())['manifest_id']


def test_missing_dmr_engine_fails_before_weight_download(tmp_path, monkeypatch):
    requests = []
    def fetch(request):
        requests.append(str(request.url))
        assert request.url.path == '/engines/status'
        return httpx.Response(200, json={'vllm': 'not installed'})
    monkeypatch.setattr('packages.parsers.model_service.download_spec', lambda _: [spec()])
    manager = Manager(tmp_path, httpx.MockTransport(fetch), dmr='http://runner')
    manager.states[(SURYA_PROFILE, 'vllm')] = {'status': 'downloading'}
    manager._prepare(SURYA_PROFILE, 'vllm')
    assert manager.state(SURYA_PROFILE, 'vllm')['code'] == 'PARSER_DMR_BACKEND_UNAVAILABLE'
    assert requests == ['http://runner/engines/status']
    assert not list(tmp_path.glob('*.json'))


def test_prepare_rejects_custom_teleocr_dmr_without_network(tmp_path):
    app = create_app(tmp_path, httpx.MockTransport(lambda req: pytest.fail('No requests')))
    with TestClient(app) as client:
        assert client.post('/models/teleocr-v1/prepare?backend=vllm').status_code == 404
        assert client.post('/models/unknown/prepare').status_code == 404


@pytest.mark.parametrize(('profile', 'code'), [
    (PROKOPE_PROFILE, 'PARSER_MODEL_ACCESS_REQUIRED'), (OXR_PROFILE, 'PARSER_MODEL_PLUGIN_REQUIRED'),
])
@pytest.mark.parametrize('backend', ['vllm', 'mlx'])
def test_unavailable_model_rejects_preparation_even_with_ready_state_and_receipt(tmp_path, monkeypatch, profile, code, backend):
    monkeypatch.delenv('PARSER_DMR_OXR', raising=False)
    app = create_app(tmp_path, httpx.MockTransport(lambda req: pytest.fail('Unavailable model cannot send requests')))
    manager = app.state.manager
    manager.states[(profile, backend)] = {'status': 'ready'}
    receipt = manager.receipt(profile, backend)
    receipt.write_bytes(canonical_bytes({'manifest_id': 'previous-or-forged-ready-receipt'}))
    original = receipt.read_bytes()
    expected = {'status': 'unavailable', 'code': code}
    with TestClient(app) as client:
        assert client.get(f'/models/{profile}?backend={backend}').json() == expected
        response = client.post(f'/models/{profile}/prepare?backend={backend}')
        assert response.status_code == 409
        assert response.json()['detail'] == expected['code']
        listed = {row['id']: row for row in client.get(f'/models?backend={backend}').json()['models']}
        assert listed[profile]['status'] == 'unavailable'
    assert receipt.read_bytes() == original
    assert sorted(path.name for path in tmp_path.iterdir()) == [receipt.name]


@pytest.mark.parametrize('mismatch', ['model_artifact_id', 'vllm_version', 'plugin_revision', 'oversize'])
def test_enabled_oxr_rejects_incompatible_runner_before_preparation(tmp_path, monkeypatch, mismatch):
    from packages.local_models.catalog import artifact
    from packages.parsers.catalog import manifest_id, vlm_model

    monkeypatch.setenv('PARSER_DMR_OXR', '1')
    model = vlm_model(OXR_PROFILE)
    requirements = model['runtime_requirements']
    capability = {'model_artifact_id': artifact(model)['id'], 'vllm_version': requirements['vllm_version'],
                  'plugin_revision': requirements['plugin_revision']}
    if mismatch == 'oversize':
        capability['extra'] = 'x' * 4096
    else:
        capability[mismatch] = 'unexpected'

    def fetch(request):
        assert request.method == 'GET' and str(request.url) == 'http://runner:12435/capabilities'
        return httpx.Response(200, json={'oxr': capability})

    app = create_app(tmp_path, httpx.MockTransport(fetch), dmr='http://runner:12434')
    manager = app.state.manager
    receipt = manager.receipt(OXR_PROFILE, 'vllm')
    receipt.write_bytes(canonical_bytes({'manifest_id': manifest_id(OXR_PROFILE)}))
    with TestClient(app) as client:
        listing = {row['id']: row for row in client.get('/models').json()['models']}
        assert listing[OXR_PROFILE]['status'] == 'unavailable'
        assert listing[OXR_PROFILE]['code'] == 'PARSER_MODEL_PLUGIN_REQUIRED'
        prepared = client.post(f'/models/{OXR_PROFILE}/prepare')
        assert prepared.status_code == 409
        assert prepared.json()['detail'] == 'PARSER_MODEL_PLUGIN_REQUIRED'
    assert not manager.states
    assert list(tmp_path.iterdir()) == [receipt]


@pytest.mark.parametrize('profile', UNAVAILABLE_PROFILES)
def test_pending_child_preparation_stops_before_control_service_or_cache_access(tmp_path, monkeypatch, profile):
    from types import SimpleNamespace
    from packages.parsers.preparation import prepare_models
    monkeypatch.setattr('httpx.Client', lambda **kwargs: pytest.fail('Unavailable models cannot contact preparation'))
    cache = tmp_path / 'absent'
    with pytest.raises(PDFError, match=UNAVAILABLE_PROFILES[profile]['code']):
        prepare_models(profile, cache, SimpleNamespace(device='dmr', backend='vllm'))
    assert not cache.exists()


def test_dmr_mode_records_exact_artifact_and_excludes_native_runtime(monkeypatch):
    from packages.parsers.runtime import runtime_config
    from packages.local_models.catalog import artifact
    from packages.parsers.catalog import vlm_model
    from packages.parsers.environment import detect_environment
    monkeypatch.setenv('PARSER_ACCELERATOR', 'dmr')
    monkeypatch.setenv('PARSER_IMAGE_FLAVOR', 'runner')
    monkeypatch.setenv('PARSER_DMR_URL', 'http://runner')
    monkeypatch.delenv('PARSER_DMR_OXR', raising=False)
    runtime = runtime_config(SURYA_PROFILE)
    assert runtime.model_id == artifact(vlm_model(SURYA_PROFILE))['id']
    assert runtime.server_url == 'http://runner/engines/vllm/v1'
    env = detect_environment()
    assert env['options'][0]['profiles'] == [profile for profile in DMR_PROFILES if profile != OXR_PROFILE]
    assert len(env['options']) == 1
    with pytest.raises(ValueError, match='PROFILE_UNAVAILABLE'):
        runtime_config('teleocr-v1')
