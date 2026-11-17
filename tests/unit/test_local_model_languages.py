from copy import deepcopy

from packages.ir import digest
from packages.local_models.catalog import artifact, models, public_models
from packages.local_models.languages import supported_target_languages, target_language_match
from packages.providers.presentation import profile_view
from packages.translation.languages import canonical_locale, check_language_policy


def test_reviewed_language_declarations_are_complete_canonical_and_family_specific():
    rows = public_models()
    by_family = {row['family']: row['supported_target_languages'] for row in rows}
    assert len(by_family['hy']) == 38
    assert len(by_family['milmmt']) == 46
    assert len(by_family['translategemma']) == 56
    assert len(by_family['plamo3']) == 53
    for row in rows:
        languages = row['supported_target_languages']
        assert languages == by_family[row['family']]
        assert len(languages) == len(set(languages))
        assert all(canonical_locale(locale) == locale for locale in languages)
        assert {'zh-Hans', 'zh-Hant', 'en'} <= set(languages)
        if row['family'] in ('hy', 'milmmt'):
            assert {'tl', 'yue'} <= set(languages)
            assert row['target_language_match'] == 'language'
        else:
            assert row['target_language_match'] == 'exact'
    assert {'gu', 'te', 'mr', 'uk', 'bo', 'mn', 'ug'} <= set(by_family['hy'])
    assert 'da' not in by_family['hy'] and 'da' in by_family['milmmt']
    assert 'uz' not in by_family['hy'] and 'uz' in by_family['milmmt']
    assert {'cs-CZ', 'fr-CA', 'fr-FR', 'pt-BR', 'pt-PT', 'is-IS'} <= set(by_family['translategemma'])
    assert 'cs' not in by_family['plamo3'] and 'pt' not in by_family['plamo3']


def test_metadata_does_not_change_model_artifact_or_frozen_profile():
    for model in models():
        original = deepcopy(model)
        identifier = artifact(model)['id']
        languages = supported_target_languages(model)
        assert model == original and artifact(model)['id'] == identifier
        if languages is not None:
            languages.clear()
            assert supported_target_languages(model)
        frozen = {'api_protocol': 'local_translation', 'model_id': identifier}
        frozen_hash = digest(frozen)
        view = profile_view(frozen)
        assert view['supported_target_languages'] == supported_target_languages(model)
        assert view['target_language_match'] == target_language_match(model)
        assert 'supported_target_languages' not in frozen
        assert 'target_language_match' not in frozen
        assert digest(frozen) == frozen_hash


def test_unknown_and_analyst_declarations_remain_unknown():
    assert supported_target_languages({'family': 'custom'}) is None
    assert supported_target_languages({'family': 'hy', 'purpose': 'analysis'}) is None
    assert all(row['supported_target_languages'] is None for row in public_models(purpose='analysis'))


def test_selector_metadata_does_not_restrict_canonical_locales_or_existing_tasks():
    source = {'language': 'en', 'blocks': [{'language': 'en', 'translatable': True}]}
    frozen = {'api_protocol': 'local_translation', 'model_id': artifact(models()[0])['id']}
    # A current selector list must not invalidate a queued task or globally gate
    # languages supported by another/custom Provider.
    check_language_policy(frozen, source, 'sr-Latn-RS')
    check_language_policy({'api_protocol': 'responses', 'model_id': 'custom'}, source, 'fil-PH')
