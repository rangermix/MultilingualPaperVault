import time
import httpx
import pytest
from packages.ir import canonical_bytes
from packages.parsers.environment import detect_environment, read_environment, resolve_accelerator
from packages.parsers.profiles import DMR_PROFILES, OXR_PROFILE, UNAVAILABLE_PROFILES


@pytest.mark.parametrize(('enabled', 'backend', 'plugin_ready', 'offers_oxr'), [
    ('0', 'vllm', True, False), ('1', 'mlx', True, False),
    ('1', 'vllm', False, False), ('1', 'vllm', True, True),
])
def test_detection_only_advertises_configured_parsers(monkeypatch, enabled, backend, plugin_ready, offers_oxr):
    from packages.local_models.catalog import artifact
    from packages.parsers.catalog import vlm_model

    monkeypatch.setenv('PARSER_DMR_OXR', enabled)
    monkeypatch.setenv('PARSER_DMR_BACKEND', backend)
    monkeypatch.setenv('PARSER_DMR_URL', 'http://runner:12434')
    model = vlm_model(OXR_PROFILE)
    requirements = model['runtime_requirements']
    requests = []

    def fetch(request):
        requests.append(request)
        assert request.method == 'GET' and str(request.url) == 'http://runner:12435/capabilities'
        if not plugin_ready:
            return httpx.Response(200, json={})
        return httpx.Response(200, json={'oxr': {
            'model_artifact_id': artifact(model)['id'], 'vllm_version': requirements['vllm_version'],
            'plugin_revision': requirements['plugin_revision'],
        }})

    client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(fetch), **kwargs))
    report = detect_environment()
    assert report['default'] == 'dmr'
    expected = [profile for profile in DMR_PROFILES if profile != OXR_PROFILE or offers_oxr]
    assert report['options'] == [{'id': 'dmr', 'profiles': expected, 'reason': None}]
    assert len(requests) == int(enabled == '1' and backend == 'vllm')


def test_current_report_and_offline_jobs_both_freeze_dmr(tmp_path):
    report = detect_environment()
    body = {'timestamp': time.time(), 'service_ready': True, 'environment': report}
    path = tmp_path / 'heartbeat.json';path.write_bytes(canonical_bytes(body))
    assert read_environment(tmp_path)['online']
    assert resolve_accelerator(DMR_PROFILES[0], tmp_path) == 'dmr'
    body['timestamp'] -= 91;path.write_bytes(canonical_bytes(body))
    assert not read_environment(tmp_path)['online']
    assert resolve_accelerator(DMR_PROFILES[0], tmp_path) == 'dmr'


@pytest.mark.parametrize('options', [[{}], [None], [{'id': 'dmr', 'profiles': 'surya'}], [{'id': 'cpu', 'profiles': []}], [{'id': 'dmr', 'profiles': ['docling-v1']}]])
def test_untrusted_or_native_heartbeat_cannot_advertise_active_capabilities(tmp_path, options):
    body = {'timestamp': time.time(), 'service_ready': True, 'environment': {
        'detected_at': time.time(), 'default': 'dmr', 'options': options}}
    (tmp_path / 'heartbeat.json').write_bytes(canonical_bytes(body))
    assert read_environment(tmp_path)['online'] is False


def test_report_missing_active_profile_fails_closed(tmp_path):
    body = {'timestamp': time.time(), 'service_ready': True, 'environment': {
        'detected_at': time.time(), 'default': 'dmr', 'options': [{'id': 'dmr', 'profiles': []}]}}
    (tmp_path / 'heartbeat.json').write_bytes(canonical_bytes(body))
    with pytest.raises(ValueError, match='PARSER_ACCELERATOR_UNAVAILABLE'):
        resolve_accelerator(DMR_PROFILES[0], tmp_path)


@pytest.mark.parametrize('profile', UNAVAILABLE_PROFILES)
def test_pending_profile_cannot_be_enabled_by_a_heartbeat_or_offline_default(tmp_path, profile):
    for online in (False, True):
        if online:
            report = detect_environment()
            report['options'][0]['profiles'].append(profile)
            (tmp_path / 'heartbeat.json').write_bytes(canonical_bytes({
                'timestamp': time.time(), 'service_ready': True, 'environment': report}))
        with pytest.raises(ValueError, match=UNAVAILABLE_PROFILES[profile]['code']):
            resolve_accelerator(profile, tmp_path)
