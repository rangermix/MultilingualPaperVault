"""Static deployment contracts; these do not certify Docker or real inference."""
import json
from pathlib import Path
import re
import tomllib

import pytest
import yaml


def compose_mode():
    return yaml.safe_load(Path('compose.example.yaml').read_text())


def test_provider_setup_uses_managed_storage_without_external_defaults():
    doc = compose_mode()
    assert not doc.get('secrets')
    for name, service in doc['services'].items():
        assert not service.get('secrets'), name
        assert not {'PROVIDER_PROFILE_FILE', 'PROVIDER_KEY_FILE'} & service.get('environment', {}).keys(), name
        mounts = service.get('volumes', [])
        assert not any('provider-profile.json' in str(v) or 'provider_key' in str(v) for v in mounts), name
        managed = [v for v in mounts if '/provider_config' in str(v)]
        if name in {'init', 'app', 'worker'}:
            assert managed == ['provider_config:/provider_config' + (':ro' if name == 'worker' else '')]
        else:
            assert not managed, name


def test_test_services_only_depend_on_their_private_database():
    doc = compose_mode()
    services = doc['services']
    assert {'tests', 'test-db', 'checks'} <= services.keys()
    assert services['tests']['profiles'] == ['tests']
    assert set(services['tests']['depends_on']) == {'test-db'}
    assert services['test-db']['profiles'] == ['tests']
    assert not services['test-db'].get('volumes')
    assert '/var/lib/postgresql/data' in services['test-db']['tmpfs']
    for name in ('tests', 'test-db'):
        assert services[name]['networks'] == ['test_backend']
    # Docker does not publish the documented host-test port on an internal-only network.
    assert not doc['networks']['test_backend'].get('internal', False)
    assert services['test-db']['ports'] == ['127.0.0.1:${TEST_DB_PORT:-55439}:5432']
    for name in ('tests', 'checks'):
        assert services[name]['build']['context'] == '.'
        assert services[name]['build']['dockerfile'] == 'tests/Dockerfile'
    checks = services['checks']
    assert checks['network_mode'] == 'none' and checks['read_only']
    assert not any(checks.get(key) for key in ('depends_on', 'volumes', 'ports', 'secrets'))


def test_optional_model_services_do_not_start_with_the_core_stack():
    services = compose_mode()['services']
    assert {'local-model-init', 'local-translator'} <= services.keys()
    for name in ('local-model-init', 'local-translator'):
        assert services[name]['profiles'] == ['local-translation']
        assert services[name]['volumes'] == ['local_translation_models:/model_cache']
    assert set(services['local-translator']['depends_on']) == {'local-model-init'}
    assert {name for name, s in services.items() if not s.get('profiles')} == {
        'init', 'db', 'migrate', 'app', 'worker', 'parser', 'parser-models', 'parser-dmr'}


def test_release_environment_example_names_are_consumed_by_production_compose():
    example = Path('.env.example').read_text()
    compose = Path('compose.example.yaml').read_text()
    documented = set(re.findall(r'^\s*(?:#\s*)?([A-Z][A-Z0-9_]*)=', example, re.MULTILINE))
    consumed = set(re.findall(r'\$\{([A-Z][A-Z0-9_]*)', compose))
    assert documented <= consumed, f'Unused deployment settings: {sorted(documented - consumed)}'


def test_one_portable_application_image_with_separate_service_boundaries():
    doc = compose_mode();services = doc['services']
    app = services['app']
    for name in ('worker', 'parser', 'parser-models', 'parser-dmr'):
        assert services[name]['image'] == app['image']
        assert services[name]['build'] == app['build']
        assert 'platform' not in services[name]
    parser, manager, relay = (services[name] for name in ('parser', 'parser-models', 'parser-dmr'))
    assert parser['environment']['PARSER_ACCELERATOR'] == 'dmr'
    assert parser['networks'] == ['parser_inference']
    assert not parser.get('network_mode')
    parser_bridge = doc['networks']['parser_inference']
    assert parser_bridge.get('driver', 'bridge') == 'bridge'
    assert parser_bridge['internal'] is True
    for family in ('ipv4', 'ipv6'):
        assert parser_bridge['driver_opts'][f'com.docker.network.bridge.gateway_mode_{family}'] == 'isolated'
    assert {name for name, service in services.items() if 'parser_inference' in service.get('networks', ())} == {
        'parser', 'parser-models', 'parser-dmr'}
    assert set(manager['networks']) == {'parser_model_control', 'parser_inference', 'model_inference'}
    assert set(relay['networks']) == {'parser_inference', 'model_inference'}
    assert not any(relay.get(key) for key in ('network_mode', 'volumes', 'volumes_from', 'ports', 'env_file', 'configs', 'secrets'))
    assert parser['environment']['PARSER_DMR_URL'] == 'http://parser-dmr:12435'
    assert parser['environment']['RESOURCE_MONITOR_URL'] == 'http://parser-dmr:12435/resources'
    upstreams = {
        'PARSER_DMR_URL': '${PARSER_DMR_URL:-http://model-runner.docker.internal}',
        'RESOURCE_MONITOR_URL': '${RESOURCE_MONITOR_URL:-http://vllm-runner:12435/resources}',
    }
    assert relay['environment'] == upstreams
    assert {key: manager['environment'][key] for key in upstreams} == upstreams
    assert services['vllm-runner']['networks'] == ['model_inference']
    for name in ('app', 'worker', 'db'):
        assert {'parser_inference', 'model_inference'}.isdisjoint(services[name]['networks']), name
    assert doc['networks']['parser_model_control']['internal'] is True
    for name in ('app', 'worker'):
        assert 'parser_model_control' in services[name]['networks'], name
    assert parser['volumes'] == ['parser_inputs:/inputs:ro', 'parser_outputs:/outputs', 'parser_models:/model_cache:ro']
    assert manager['volumes'] == ['parser_models:/model_cache']
    assert not any(parser.get(k) or manager.get(k) for k in ('ports', 'secrets', 'models'))
    assert not Path('deployment/images/parser.Dockerfile').exists()
    recipe = Path('deployment/images/app.Dockerfile').read_text()
    assert 'download_parser_models' not in recipe and 'COPY --from=models' not in recipe


def test_parser_lock_contains_no_native_frameworks_or_archived_models():
    packages = {row['name'] for row in tomllib.loads(Path('uv.lock').read_text())['package']}
    assert not packages & {'docling', 'torch', 'transformers', 'onnxruntime', 'paddlepaddle', 'paddleocr', 'paddlex', 'opencv-contrib-python'}
    vision = json.loads(Path('deployment/parser-vlm-models.lock.json').read_text())
    assert {model['id'] for model in vision['models']} == {'surya-ocr-2-v1', 'chandra-ocr-2-v1', 'infinity-parser2-pro-v1', 'infinity-parser2-flash-v1', 'oxr-1.0-v1'}
    oxr = next(model for model in vision['models'] if model['id'] == 'oxr-1.0-v1')
    assert oxr['revision'] == 'c708407f9d2b4df658f2543d9132b62bb7221df4'
    assert oxr['runtime_requirements']['plugin_revision'] == oxr['revision']
    assert oxr['runtime_requirements']['vllm_version'] == '0.25.1'
    assert not Path('deployment/parser-models.lock.json').exists()
    assert 'archive' in Path('.dockerignore').read_text().splitlines()
