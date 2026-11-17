"""Response-only names for the exact local model in a confirmed profile."""
from packages.local_models.catalog import get_model
from packages.local_models.languages import supported_target_languages, target_language_match


def profile_view(profile):
    """Keep the profile and its digest inputs unchanged; never read current settings."""
    result = dict(profile)
    result.pop('model_display_name', None)
    # Response metadata never enters a saved profile, hash, or queued snapshot.
    # Arbitrary API model IDs have no reviewed language declaration.
    result['supported_target_languages'] = None
    result['target_language_match'] = 'language'
    if profile.get('api_protocol') == 'local_translation' and profile.get('model_id'):
        try:
            model = get_model(profile['model_id'])
        except ValueError:
            pass
        else:
            result['model_display_name'] = model['label']
            result['supported_target_languages'] = supported_target_languages(model)
            result['target_language_match'] = target_language_match(model)
    return result
