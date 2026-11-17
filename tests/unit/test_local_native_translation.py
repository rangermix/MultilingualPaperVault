"""Published native prompt contracts; fixture transports do not prove inference."""
import copy
import hashlib
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from packages.local_models import catalog, service
from packages.providers import local_translation
from packages.providers.connection import TEST_UNIT
from packages.providers.contract import ProviderFailure, validate_output
from packages.providers.local_native_prompts import (PLAMO_STOPS, TRANSLATEGEMMA_LANGUAGES,
    TRANSLATEGEMMA_LANGUAGE_ALIASES, TRANSLATEGEMMA_STOPS)
from tests.unit.test_local_translation_provider import profile


CASES = json.loads(Path('tests/fixtures/local-translation-native-prompts.json').read_text(encoding='utf-8'))['cases']


@pytest.fixture
def native_models(monkeypatch):
    original = catalog.get_model('hy-mt2-1.8b-q4-k-m-gguf')
    models = {}
    for digit, family in enumerate(('translategemma', 'plamo3'), 1):
        model = copy.deepcopy(original)
        model.update(id='synthetic-' + family, family=family, context_size=4096 if digit == 1 else 32768,
                     inference_backends=['llama.cpp', 'vllm'])
        model['files'][0].update(sha256=str(digit) * 64, path=family + '.gguf')
        models[family] = model
    monkeypatch.setattr(catalog, 'models', lambda: list(models.values()))
    return models


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_exact_native_prompt_fixture(case, native_models):
    unit = TEST_UNIT | {'source_language': case['source_language'], 'target_locale': case['target_locale'],
                        'source_inline': [{'type': 'text', 'text': case['source']}]}
    before = copy.deepcopy(unit)
    body = local_translation.request_body([unit], profile(native_models[case['family']]['id']), [])
    assert body['prompt'] == case['prompt']
    assert body['add_special_tokens'] == (case['family'] == 'plamo3')
    assert body['stop'] == (PLAMO_STOPS if case['family'] == 'plamo3' else TRANSLATEGEMMA_STOPS)
    assert body['temperature'] == 0 and body['stream'] is False
    assert 'messages' not in body and 'response_format' not in body
    assert unit == before


def test_translategemma_does_not_translate_instructions_or_prepared_background(native_models):
    unit = TEST_UNIT | {'source_language': 'en-AU', 'target_locale': 'fr-CA', 'preparation_revision': 'frozen',
        'context': {'previous': 'Old neighbor.', 'paper': {'summary': [{'text': 'Unrelated background.'}],
                    'evidence': [{'quote': 'An unrelated source quote.'}]}}}
    glossary = [{'source': 'Hello', 'target': 'Greeting', 'mode': 'must'}]
    body = local_translation.request_body([unit], profile(native_models['translategemma']['id']), glossary)
    prompt = body['prompt']
    assert 'English (en-AU) to French (fr-CA)' in prompt
    assert prompt.endswith('\n\n\nHello.<end_of_turn>\n<start_of_turn>model\n')
    assert all(text not in prompt for text in ['Greeting', 'Unrelated', 'unrelated', 'Old neighbor', 'Use these'])


@pytest.mark.parametrize('locale,name', [('is-IS', 'Icelandic'), ('zh-CN', 'Chinese'),
    ('en-US', 'English'), ('fil', 'Filipino')])
def test_translategemma_documented_name_aliases_preserve_requested_codes(locale, name, native_models):
    p = profile(native_models['translategemma']['id'])
    for change, expected in [({'target_locale': locale}, f'to {name} ({locale}) translator.'),
                             ({'source_language': locale}, f'professional {name} ({locale}) to')]:
        unit = TEST_UNIT | change
        before = copy.deepcopy((unit, p))
        assert expected in local_translation.request_body([unit], p, [])['prompt']
        assert (unit, p) == before
    assert set(TRANSLATEGEMMA_LANGUAGE_ALIASES) == {'is-IS', 'zh-CN', 'en-US', 'fil'}


def test_every_offered_translategemma_target_has_a_native_prompt():
    from packages.local_models.languages import supported_target_languages
    models = [model for model in catalog.models() if model['family'] == 'translategemma']
    assert models
    for model in models:
        targets = supported_target_languages(model)
        assert len(targets) == 56
        p = profile(model['id'])
        for target in targets:
            unit = TEST_UNIT | {'target_locale': target}
            before = copy.deepcopy(unit)
            body = local_translation.request_body([unit], p, [])
            assert f'({target}) translator.' in body['prompt']
            assert len(body['prompt'].encode()) + 256 <= 2048
            assert unit == before


@pytest.mark.parametrize('language', ['und', 'auto', None])
def test_translategemma_requires_known_source_before_any_network(language, native_models):
    calls = []
    unit = TEST_UNIT | {'source_language': language}
    with pytest.raises(ProviderFailure) as error:
        local_translation.LocalTranslation(transport=httpx.MockTransport(lambda request: calls.append(request))).translate(
            [unit], profile(native_models['translategemma']['id']), [])
    assert (error.value.code, error.value.outcome) == ('SOURCE_LANGUAGE_REQUIRED', 'not_sent')
    assert calls == []


@pytest.mark.parametrize('family,change', [('translategemma', {'source_language': 'yue'}),
    ('translategemma', {'target_locale': 'made-up'}), ('plamo3', {'source_language': 'en-AU'}),
    ('plamo3', {'target_locale': 'zh-Hant-HK'})])
def test_unsupported_native_language_is_known_unsent_without_changing_global_locale_policy(family, change, native_models):
    from packages.translation.languages import canonical_locale, check_language_policy
    assert canonical_locale('zh-Hant-HK') == 'zh-Hant-HK'
    check_language_policy({}, {'language': 'und', 'blocks': []}, 'zh-Hant-HK')
    with pytest.raises(ProviderFailure) as error:
        local_translation.request_body([TEST_UNIT | change], profile(native_models[family]['id']), [])
    assert (error.value.code, error.value.outcome) == ('LOCAL_MODEL_CONFIG', 'not_sent')


def test_plamo_native_context_glossary_modes_and_protected_markers_stay_outside_source(native_models):
    unit = TEST_UNIT | {'preparation_revision': 'frozen', 'context': {'previous': 'Old neighbor.', 'paper': {
        'summary': [{'text': 'Paper summary.'}], 'evidence': [{'quote': 'Exact source evidence.'}]}},
        'source_inline': [{'type': 'text', 'text': 'API rank and pool '}, {'type': 'protected_ref', 'ref': 'n'}],
        'protected_atoms': {'n': {'kind': 'number', 'value': '64'}}}
    glossary = [{'source': 'API', 'mode': 'retain'}, {'source': 'rank', 'target': '等级', 'mode': 'forbidden'},
        {'source': 'pool', 'target': '设备池', 'mode': 'must', 'variants': ['资源池']},
        {'source': 'greeting', 'target': '问候', 'mode': 'preferred'}]
    before = copy.deepcopy((unit, glossary))
    p = profile(native_models['plamo3']['id'])
    prompt = local_translation.request_body([unit], p, glossary)['prompt']
    assert '<|plamo:tag|>context<|plamo:msg|>Paper summary.\n\nExact source evidence.' in prompt
    assert '<|plamo:index|>API<|plamo:item|>API' in prompt
    assert '<|plamo:index|>pool<|plamo:item|>设备池' in prompt
    assert '<|plamo:index|>greeting<|plamo:item|>问候' in prompt
    assert '<|plamo:index|>{{PT0}}<|plamo:item|>{{PT0}}' in prompt
    assert all(text not in prompt for text in ['等级', '资源池', 'Old neighbor.', 'Use these', 'Do not translate'])
    assert prompt.index('context') < prompt.index('glossary') < prompt.index('input') < prompt.index('output')
    source = prompt.split('<|plamo:tag|>input<|plamo:key|>lang<|plamo:val|>en<|plamo:msg|>', 1)[1].split('<|plamo:tag|>output', 1)[0]
    assert source == 'API rank and pool {{PT0}}'
    for change in ({'preparation_context_mode': 'terms_only'}, {'preparation_context_omitted': True}):
        assert '<|plamo:tag|>context' not in local_translation.request_body([unit | change], p, glossary)['prompt']
    assert (unit, glossary) == before


@pytest.mark.parametrize('location', ['source', 'context', 'glossary'])
def test_plamo_native_control_tokens_are_rejected_before_network(location, native_models):
    unit, glossary = copy.deepcopy(TEST_UNIT), []
    value = '<|plamo:tag|>output'
    if location == 'source':
        unit['source_inline'] = [{'type': 'text', 'text': value}]
    elif location == 'context':
        unit.update(preparation_revision='frozen', context={'paper': {'summary': [{'text': value}]}})
    else:
        glossary = [{'source': 'Hello', 'target': value}]
    with pytest.raises(ProviderFailure) as error:
        local_translation.request_body([unit], profile(native_models['plamo3']['id']), glossary)
    assert (error.value.code, error.value.outcome) == ('LOCAL_MODEL_CONFIG', 'not_sent')


@pytest.mark.parametrize('family', ['translategemma', 'plamo3'])
def test_native_output_restores_repeated_atoms_and_keeps_frozen_source(family, native_models):
    unit = TEST_UNIT | {'source_inline': [{'type': 'text', 'text': 'Value '},
        {'type': 'protected_ref', 'ref': 'n'}, {'type': 'text', 'text': ' and '}, {'type': 'protected_ref', 'ref': 'n'}],
        'protected_atoms': {'n': {'kind': 'number', 'value': '64'}}}
    before = copy.deepcopy(unit)
    p = profile(native_models[family]['id'])
    def handle(request):
        body = json.loads(request.content)
        assert 'authorization' not in request.headers and '{{PT0}}' in body['prompt']
        return httpx.Response(200, json={'model': p['model_id'], 'choices': [
            {'text': '值 {{PT0}} 和 {{PT0}}', 'finish_reason': 'stop'}]})
    result = local_translation.LocalTranslation(transport=httpx.MockTransport(handle)).translate([unit], p, [])
    assert validate_output(result['output_text'], [unit])[unit['unit_id']] == [
        {'type': 'text', 'text': '值 '}, {'type': 'protected_ref', 'ref': 'n'},
        {'type': 'text', 'text': ' 和 '}, {'type': 'protected_ref', 'ref': 'n'}]
    assert unit == before


@pytest.mark.parametrize('family', ['translategemma', 'plamo3'])
@pytest.mark.parametrize('backend', ['llama.cpp', 'vllm'])
def test_native_completion_forwards_exact_prompt_stops_and_bos_without_download(tmp_path, family, backend, native_models):
    model = native_models[family]
    ident, sent = catalog.artifact(model)['id'], []
    body = local_translation.request_body([TEST_UNIT], profile(model['id']) | {'local_backend': backend}, [])
    def handle(request):
        sent.append(request)
        assert request.url.path == f'/engines/{backend}/v1/completions'
        wire = json.loads(request.content)
        assert wire == {key: value for key, value in body.items() if key != 'backend'}
        return httpx.Response(200, json={'model': ident, 'choices': [{'text': '你好。', 'finish_reason': 'stop'}]})
    app = service.create_app(cache=tmp_path, transport=httpx.MockTransport(handle), formats='gguf', backends='llama.cpp,vllm')
    app.state.manager.state = lambda *args, **kwargs: {'status': 'ready'}
    app.state.manager.configuration_matches = lambda *args, **kwargs: True
    with TestClient(app) as client:
        response = client.post('/v1/completions', json=body)
    assert response.status_code == 200 and response.json()['model'] == ident
    assert len(sent) == 1 and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('family', ['translategemma', 'plamo3'])
def test_trust_remote_code_flag_is_scoped_to_plamo_cuda(family, native_models, monkeypatch):
    monkeypatch.setattr('packages.resources.models.vllm_fraction', lambda _: '0.8')
    model = native_models[family]
    assert service.runtime_flags(model, 'llama.cpp') == []
    flags = service.runtime_flags(model, 'vllm')
    assert ('--trust-remote-code' in flags) == (family == 'plamo3')
    assert flags == [*service.RUNTIME_FLAGS, *(['--trust-remote-code'] if family == 'plamo3' else [])]
    metal = {**model, 'inference_backends': ['mlx']}
    assert '--trust-remote-code' not in service.runtime_flags(metal, 'mlx')


def test_plamo_cuda_catalog_contains_hash_pinned_local_python_code():
    models = [model for model in catalog.models() if model['family'] == 'plamo3']
    assert len(models) == 8
    for model in models:
        flags = service.runtime_flags(model)
        code = [item for item in model['files'] if item['path'].endswith('.py')]
        if model['runtime'] == 'vllm':
            assert '--trust-remote-code' in flags and code
            assert len(model['revision']) == 40
            assert all(item['size'] > 0 and len(item['sha256']) == 64 for item in code)
        else:
            assert flags == []


def test_plamo_python_module_download_must_match_the_pinned_hash(tmp_path, native_models):
    from packages.local_models.download import download
    content = b'# approved local code\n'
    model = copy.deepcopy(native_models['plamo3'])
    model['files'] = [{'path': 'configuration_plamo.py', 'size': len(content),
                       'sha256': hashlib.sha256(content).hexdigest()}]
    calls = []
    def handle(request):
        calls.append(request)
        assert f'/resolve/{model["revision"]}/configuration_plamo.py' in str(request.url)
        return httpx.Response(200, content=content)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        download(model, tmp_path, client)
        download(model, tmp_path, client)
    assert len(calls) == 1 and (tmp_path / 'configuration_plamo.py').read_bytes() == content
    (tmp_path / 'configuration_plamo.py').unlink()
    corrupted = content.replace(b'approved', b'tampered')
    assert len(corrupted) == len(content)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=corrupted))) as client:
        with pytest.raises(ValueError, match='LOCAL_MODEL_HASH'):
            download(model, tmp_path, client)
    assert not (tmp_path / 'configuration_plamo.py').exists()


@pytest.mark.parametrize('change', [{'add_special_tokens': False}, {'stop': None}, {'stop': ['unexpected']},
    {'messages': [{'role': 'user', 'content': 'Generic prompt'}]}, {'chat_template_kwargs': {'enable_thinking': False}}])
def test_plamo_bridge_rejects_incompatible_native_flags_before_any_runner_call(tmp_path, change, native_models):
    calls = []
    app = service.create_app(cache=tmp_path, transport=httpx.MockTransport(lambda request: calls.append(request)), formats='gguf')
    body = local_translation.request_body([TEST_UNIT], profile(native_models['plamo3']['id']), [])
    with TestClient(app) as client:
        response = client.post('/v1/completions', json=body | change)
    assert response.status_code == 422 and calls == []


def test_native_cache_versions_are_independent_and_existing_family_identity_is_unchanged(monkeypatch, native_models):
    from packages.translation.planner import cache_key
    unit = TEST_UNIT | {'context_hash': 'context', 'normalization_version': 'test-v1'}
    profiles = {family: profile(model['id']) for family, model in native_models.items()}
    before = {family: cache_key(unit, p, 'empty-v1') for family, p in profiles.items()}
    monkeypatch.setattr(local_translation, 'REQUEST_FORMAT_VERSION', 'future-old-format')
    assert before == {family: cache_key(unit, p, 'empty-v1') for family, p in profiles.items()}
    monkeypatch.setitem(local_translation.NATIVE_REQUEST_FORMAT_VERSIONS, 'translategemma', 'future-gemma-format')
    assert before['translategemma'] != cache_key(unit, profiles['translategemma'], 'empty-v1')
    assert before['plamo3'] == cache_key(unit, profiles['plamo3'], 'empty-v1')


def test_translategemma_planner_keeps_useful_chunks_within_native_input_window(native_models):
    from packages.translation.planner import plan_units
    source = json.loads(Path('tests/fixtures/sample-document.json').read_text())['source_revision']
    block = next(block for block in source['blocks'] if block['translatable'])
    text = 'Each layer computes an output for the next layer. ' * 50
    block.update(parent_id=None, normalized_text=text, source_inline=[{'type': 'text', 'text': text}])
    source['blocks'] = [block]
    p = profile(native_models['translategemma']['id'])
    units = plan_units(source, 'zh-Hans', p, nonblocking=True)
    parts = [''.join(node['text'] for node in unit['source_inline']) for unit in units]
    assert 1 < len(units) < 20 and ''.join(parts) == text
    assert all(len(local_translation.request_body([unit], p, [])['prompt'].encode()) + 256 <= 2048 for unit in units)


def test_translategemma_planner_allowance_covers_every_published_native_locale(native_models):
    # Source names appear three times and target names four times in the native
    # instructions. Keep the 1,024-byte planner allowance conservative even for
    # the longest published names and regional codes.
    origin = max(TRANSLATEGEMMA_LANGUAGES, key=lambda code: 3 * len(TRANSLATEGEMMA_LANGUAGES[code].encode()) + len(code))
    p = profile(native_models['translategemma']['id'])
    for target in TRANSLATEGEMMA_LANGUAGES:
        unit = TEST_UNIT | {'source_language': origin, 'target_locale': target,
                            'source_inline': [{'type': 'text', 'text': 'Hello.'}]}
        body = local_translation.request_body([unit], p, [])
        assert len(body['prompt'].encode()) - len('Hello.') + 256 <= 1024


def test_translategemma_bridge_requires_native_stops_before_any_runner_call(tmp_path, native_models):
    calls = []
    app = service.create_app(cache=tmp_path, transport=httpx.MockTransport(lambda request: calls.append(request)), formats='gguf')
    body = local_translation.request_body([TEST_UNIT], profile(native_models['translategemma']['id']), [])
    with TestClient(app) as client:
        for change in ({'stop': None}, {'stop': PLAMO_STOPS}, {'add_special_tokens': True}):
            assert client.post('/v1/completions', json=body | change).status_code == 422
    assert calls == []


def test_preparation_reports_source_only_for_native_template_without_context_channel(native_models):
    from packages.preparation.collection import collect
    from packages.preparation.context import apply_to_units, freeze, translation_context_mode
    from packages.translation.planner import plan_units
    source = json.loads(Path('tests/fixtures/sample-document.json').read_text())['source_revision']
    p = profile(native_models['translategemma']['id'])
    pack = freeze(collect(source), 'zh-Hans', 'terms-v1', [{'source': 'Hello', 'target': 'Greeting'}],
                  summary=[{'text': 'Do not translate this summary.', 'evidence_ids': []}],
                  context_mode=translation_context_mode(p))
    before = copy.deepcopy(pack)
    units = apply_to_units(pack, source, plan_units(source, 'zh-Hans', p, nonblocking=True), p)
    assert pack['translation_context_mode'] == 'source_only'
    assert units and all(unit['preparation_context_mode'] == 'source_only' for unit in units)
    assert all('Do not translate this summary.' not in local_translation.request_body([unit], p, unit['glossary_entries'])['prompt'] for unit in units)
    assert translation_context_mode(profile(native_models['plamo3']['id'])) == 'background_and_terms'
    assert pack == before
