"""Pinned parser artifacts. Importing or listing this catalogue never downloads."""
from functools import lru_cache

from packages.ir import digest, strict_loads
from packages.paths import ROOT
from .profiles import PARSER_PROFILES, UNAVAILABLE_PROFILES, selected_profile, unavailable_code

VLM_LOCK_PATH = ROOT / 'deployment/parser-vlm-models.lock.json'


@lru_cache
def vlm_lock():
    return strict_loads(VLM_LOCK_PATH.read_bytes())


def vlm_model(profile):
    selected_profile({'parser_profile_revision': profile})
    for model in vlm_lock()['models']:
        if model['id'] == profile:
            return model
    raise ValueError(UNAVAILABLE_PROFILES[profile]['code'])


def download_spec(profile):
    """Flatten the selected pinned full-page model into cache-relative files."""
    model = vlm_model(profile)
    prefix = model['repo'].replace('/', '--') + '/' + model['revision']
    return [{'path': prefix + '/' + f['path'], 'size': f['size'], 'sha256': f['sha256'],
             'url': f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{f['path']}"}
            for f in model['files']]


def manifest_id(profile):
    return digest(download_spec(profile))


def public_models(backend=None):
    from packages.resources.models import reference
    result = []
    for row in PARSER_PROFILES:
        unavailable = UNAVAILABLE_PROFILES.get(row['id'])
        if unavailable and not any(m['id'] == row['id'] for m in vlm_lock()['models']):
            result.append({**row, **unavailable, 'availability': 'unavailable',
                'status': 'unavailable', 'download_bytes': None, 'manifest_id': None,
                'license': None, 'memory_reference': None})
            continue
        spec = download_spec(row['id'])
        model = vlm_model(row['id'])
        code = unavailable_code(row['id'], backend)
        result.append({**row, 'download_bytes': sum(f['size'] for f in spec),
                       'model_id': model['repo'],
                       'revision': model.get('revision'), 'license': model.get('license'),
                       'manifest_id': digest(spec), 'memory_reference': reference(model),
                       **({'availability': 'unavailable', 'status': 'unavailable',
                           'code': code} if code else {})})
    return result
