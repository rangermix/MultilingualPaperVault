"""The portable client delegates inference without silently retargeting old jobs."""
import sys
import pytest
from packages.parsers.catalog import vlm_model
from packages.local_models.catalog import artifact
from packages.parsers.profiles import DMR_PROFILES, OXR_PROFILE, RETIRED_PROFILES, UNAVAILABLE_PROFILES
from packages.parsers.runtime import runtime_config, child_executable
from packages.parsers.progress import local_identity
from packages.domain.workflow import ModelIdentity


@pytest.mark.parametrize('backend', ['vllm', 'mlx'])
@pytest.mark.parametrize('profile', [profile for profile in DMR_PROFILES if profile != OXR_PROFILE])
def test_stock_parsers_use_exact_dmr_artifact_on_either_declared_backend(monkeypatch, profile, backend):
    monkeypatch.setenv('PARSER_DMR_BACKEND', backend)
    monkeypatch.setenv('PARSER_DMR_URL', 'http://runner')
    runtime = runtime_config(profile, 'dmr')
    assert runtime.model_id == artifact(vlm_model(profile))['id']
    assert runtime.server_url == 'http://runner/engines/vllm/v1'
    identity = ModelIdentity.model_validate(local_identity(profile, {}))
    assert identity.device == 'dmr' and identity.model_id == vlm_model(profile)['repo']
    assert identity.engine_version is None  # Client metadata is not package-version proof.
    assert child_executable(profile, 'dmr') == sys.executable


@pytest.mark.parametrize(('enabled', 'backend', 'allowed'), [
    ('0', 'vllm', False), ('1', 'mlx', False), ('1', 'vllm', True),
])
def test_oxr_runtime_requires_opt_in_and_vllm(monkeypatch, enabled, backend, allowed):
    monkeypatch.setenv('PARSER_DMR_OXR', enabled)
    monkeypatch.setenv('PARSER_DMR_BACKEND', backend)
    monkeypatch.setenv('PARSER_DMR_URL', 'http://runner')
    monkeypatch.setattr('httpx.Client', lambda **kwargs: pytest.fail('Runtime selection must not contact a runner'))
    if not allowed:
        with pytest.raises(ValueError, match='^PARSER_MODEL_PLUGIN_REQUIRED$'):
            child_executable(OXR_PROFILE, 'dmr')
        return
    runtime = runtime_config(OXR_PROFILE, 'dmr')
    assert runtime.model_id == artifact(vlm_model(OXR_PROFILE))['id']
    assert runtime.server_url == 'http://runner/engines/vllm/v1'
    assert runtime.backend == 'vllm'
    assert child_executable(OXR_PROFILE, 'dmr') == sys.executable


@pytest.mark.parametrize('device', ['cpu', 'cuda', 'mlx'])
def test_native_snapshot_is_rejected_instead_of_silently_moved_to_dmr(device):
    with pytest.raises(ValueError, match='PARSER_NATIVE_RUNTIME_RETIRED'):
        runtime_config(DMR_PROFILES[0], device)


@pytest.mark.parametrize('profile', RETIRED_PROFILES)
def test_retired_model_cannot_reenter_through_runtime_configuration(profile):
    with pytest.raises(ValueError, match='PARSER_PROFILE_UNAVAILABLE'):
        runtime_config(profile, 'dmr')


def test_backend_change_cannot_redirect_a_frozen_job(monkeypatch):
    monkeypatch.setenv('PARSER_DMR_BACKEND', 'mlx')
    with pytest.raises(ValueError, match='PARSER_BACKEND_CHANGED'):
        runtime_config('surya-ocr-2-v1', 'dmr', 'vllm')


def test_invalid_backend_does_not_report_an_oxr_prerequisite(monkeypatch):
    from packages.parsers.errors import MESSAGES
    monkeypatch.setenv('PARSER_DMR_BACKEND', 'unknown')
    with pytest.raises(ValueError, match='^PARSER_MODEL_BACKEND_UNSUPPORTED$'):
        runtime_config('surya-ocr-2-v1')
    assert 'OXR' not in MESSAGES['PARSER_MODEL_BACKEND_UNSUPPORTED']


@pytest.mark.parametrize('profile', UNAVAILABLE_PROFILES)
@pytest.mark.parametrize('backend', ['vllm', 'mlx'])
def test_pending_profile_cannot_execute_on_either_backend(profile, backend, monkeypatch):
    monkeypatch.setenv('PARSER_DMR_BACKEND', backend)
    monkeypatch.setattr('httpx.Client', lambda **kwargs: pytest.fail('Unavailable models must not contact a runner'))
    for configure in (runtime_config, child_executable):
        with pytest.raises(ValueError, match=UNAVAILABLE_PROFILES[profile]['code']):
            configure(profile, 'dmr')
