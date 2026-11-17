"""Offline integrity and attribution coverage for shipped third-party resources."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

import pytest

from packages.domain.errors import DomainError
from packages.parsers.page_prompts import CHANDRA_LAYOUT_PROMPT
from packages.seed.legacy import checked_release, omitted_adaptations
from packages.seed import legal


ROOT = Path(__file__).resolve().parents[2]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_chandra_prompt_and_license_are_bound_to_reviewed_upstream_bytes():
    root = ROOT / 'res/vendor/chandra-prompts'
    provenance = json.loads((root / 'provenance.json').read_text('utf-8'))
    assert provenance['license'] == 'Apache-2.0'
    assert provenance['revision'] == 'd4f7467435aa4137d9539f000ddf0b7ced3eb43f'
    assert sha256(root / 'LICENSE') == provenance['license_sha256']
    assert 'Copyright 2025 Endless Labs, Inc.' in (root / 'LICENSE').read_text('utf-8')
    normalized = re.sub(r'\s+', ' ', CHANDRA_LAYOUT_PROMPT).strip().encode('utf-8')
    assert hashlib.sha256(normalized).hexdigest() == provenance['normalized_prompt_sha256']
    assert provenance['local_source'] == 'src/packages/parsers/page_prompts.py'


def test_seed_attribution_covers_exact_frozen_documents_and_payloads():
    root = ROOT / 'res/reference'
    release = checked_release(allow_omitted_adaptations=True)
    omitted = omitted_adaptations(release)
    provenance = json.loads((root / 'legacy-provenance.json').read_text('utf-8'))
    papers = {paper['id']: paper for paper in provenance['documents']}
    assert set(papers) == {paper['id'] for paper in release['documents']}
    notice = (root / 'legacy-NOTICE.md').read_text('utf-8')
    assert sha256(root / 'CC-BY-4.0.txt') == provenance['license_sha256']
    for seed in release['documents']:
        paper = papers[seed['id']]
        assert paper['source_license'] == 'CC-BY-4.0'
        assert paper['title'] == seed['title']
        assert paper['source_path'] == seed['source_path']
        assert sha256(ROOT / 'res' / paper['source_path']) == paper['source_sha256']
        assert paper['source_url'].endswith(paper['arxiv_id'])
        assert paper['record_url'].endswith(paper['arxiv_id'])
        assert paper['arxiv_id'] in notice
        assert all(author in notice for author in paper['authors'])
        assert paper['translation']['individual_translator'] is None
        assert paper['translation']['generation_method'] is None
        assert paper['translation']['human_review'] is None
        assert {entry['path']: entry['sha256'] for entry in paper['files']} == {
            entry['path']: entry['sha256'] for entry in seed['files']}
        for entry in paper['files']:
            if entry['path'] not in omitted:
                assert sha256(ROOT / 'res' / entry['path']) == entry['sha256']
    legal.checked_legal(release)


def test_seed_legal_resources_reject_changed_license_bytes(tmp_path, monkeypatch):
    changed = tmp_path / 'changed-license.txt'
    changed.write_text('Unreviewed replacement terms', encoding='utf-8')
    original = legal.safe_path
    monkeypatch.setattr(legal, 'safe_path', lambda root, relative, **kwargs:
                        changed if str(relative) == 'reference/CC-BY-4.0.txt'
                        else original(root, relative, **kwargs))
    with pytest.raises(DomainError) as caught:
        legal.checked_legal(checked_release(allow_omitted_adaptations=True))
    assert caught.value.code == 'LEGACY_LICENSE_HASH_MISMATCH'


def test_notice_links_resolve_in_the_application_image_resource_layout():
    notices = ROOT / 'THIRD_PARTY_NOTICES.md'
    text = notices.read_text('utf-8')
    assert 'SIL Open Font License' in text and 'CC BY 4.0' in text
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', text):
        url = urlsplit(target)
        if url.scheme or url.netloc:
            assert url.scheme == 'https' and url.hostname, target
            continue
        path = (ROOT / url.path).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(), target
