"""The release seed cannot detach a trusted file list from the bytes it imports."""
import copy
import json
from shutil import copyfile

import pytest

from packages.domain.errors import DomainError
import packages.seed.legacy as legacy


@pytest.mark.parametrize('field,value', [
    ('html_path', 'fixtures/unknown-unreviewed.html'),
    ('source_path', '/tmp/unreviewed-source.pdf'),
])
def test_legacy_entry_paths_cannot_bypass_the_hashed_file_list(monkeypatch, field, value):
    # Synthetic in-memory release metadata: never change the reference package.
    frozen = (legacy.ROOT / 'res/reference/legacy-manifest.json').read_bytes()
    changed = copy.deepcopy(json.loads(frozen))
    changed['documents'][0][field] = value
    original = legacy.strict_loads
    monkeypatch.setattr(legacy, 'strict_loads', lambda content: changed if content == frozen else original(content))
    with pytest.raises(DomainError) as caught:
        legacy.checked_release()
    assert caught.value.code == 'LEGACY_MANIFEST_INVALID'


def test_changed_legacy_source_bytes_are_rejected_without_touching_the_reference(tmp_path, monkeypatch):
    release = json.loads((legacy.ROOT / 'res/reference/legacy-manifest.json').read_bytes())
    path = release['documents'][0]['source_path']
    original_bytes = (legacy.RESOURCE_ROOT / path).read_bytes()
    changed = tmp_path / 'changed-source.pdf'
    changed.write_bytes(original_bytes + b'\nChanged unreviewed bytes')
    original_safe_path = legacy.safe_path
    monkeypatch.setattr(legacy, 'safe_path', lambda root, relative, **kwargs:
        changed if str(relative) == path else original_safe_path(root, relative, **kwargs))
    with pytest.raises(DomainError) as caught:
        legacy.checked_release()
    assert caught.value.code == 'LEGACY_HASH_MISMATCH'
    assert (legacy.RESOURCE_ROOT / path).read_bytes() == original_bytes


def test_adaptation_omission_requires_marker_and_all_payload_absent(tmp_path, monkeypatch):
    release = legacy.checked_release(allow_omitted_adaptations=True)
    originals = {paper['source_path'] for paper in release['documents']}
    required = originals | {
        'reference/legacy-manifest.json',
        'reference/reference-files.sha256.json',
        'reference/reader-v1.css',
    }
    resource_dir = tmp_path / 'res'
    for relative in required:
        target = resource_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(legacy.RESOURCE_ROOT / relative, target)

    monkeypatch.setattr(legacy, 'ROOT', tmp_path)
    monkeypatch.setattr(legacy, 'RESOURCE_ROOT', resource_dir)
    marker = resource_dir / legacy.OMISSION_NOTICE
    marker.write_text('Optional adaptations intentionally omitted.', encoding='utf-8')

    assert legacy.checked_release(allow_omitted_adaptations=True) == release
    with pytest.raises(DomainError) as omitted:
        legacy.checked_release()
    assert omitted.value.code == 'LEGACY_SEED_BUNDLE_NOT_INCLUDED'

    html = resource_dir / release['documents'][0]['html_path']
    html.write_text('Unverified partial bundle', encoding='utf-8')
    with pytest.raises(DomainError) as partial:
        legacy.checked_release(allow_omitted_adaptations=True)
    assert partial.value.code in {'ASSET_MISSING', 'LEGACY_HASH_MISMATCH'}

    html.unlink()
    marker.unlink()
    with pytest.raises(DomainError) as missing:
        legacy.checked_release(allow_omitted_adaptations=True)
    assert missing.value.code == 'ASSET_MISSING'
