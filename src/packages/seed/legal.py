"""Hash-bound legal companions for newly generated controlled seed artifacts."""
from html import escape
import json

from packages.domain.errors import require
from packages.ir import canonical_bytes, digest, strict_loads
from packages.paths import RESOURCE_ROOT
from packages.storage import safe_path


PROVENANCE_SHA256 = '93f3d8537bba0cb58974c3f1749fb7cbe2614f367ac81fbd22a5ff6a75b12c3c'


def checked_legal(release):
    raw = safe_path(RESOURCE_ROOT, 'reference/legacy-provenance.json').read_bytes()
    require(digest(raw) == PROVENANCE_SHA256, 'LEGACY_PROVENANCE_INVALID')
    provenance = strict_loads(raw)
    papers = {paper['id']: paper for paper in provenance['documents']}
    require(set(papers) == {seed['id'] for seed in release['documents']}, 'LEGACY_PROVENANCE_INVALID')
    for seed in release['documents']:
        paper = papers[seed['id']]
        require(paper['source_path'] == seed['source_path'] and paper['title'] == seed['title']
                and {row['path']: row['sha256'] for row in paper['files']}
                == {row['path']: row['sha256'] for row in seed['files']}, 'LEGACY_PROVENANCE_INVALID')
    license_text = safe_path(RESOURCE_ROOT, 'reference/CC-BY-4.0.txt').read_bytes()
    notice = safe_path(RESOURCE_ROOT, 'reference/legacy-NOTICE.md').read_bytes()
    release_bytes = safe_path(RESOURCE_ROOT, 'reference/legacy-manifest.json').read_bytes()
    require(digest(license_text) == provenance['license_sha256']
            and digest(notice) == provenance['notice_sha256'], 'LEGACY_LICENSE_HASH_MISMATCH')
    require(strict_loads(release_bytes) == release, 'LEGACY_PROVENANCE_INVALID')
    return provenance, license_text, notice, release_bytes


def with_attribution(page, item, legal):
    """Embed notices for single HTML and retain companion files for ZIP exports."""
    provenance, license_text, notice, release_bytes = legal
    paper = next(paper for paper in provenance['documents'] if paper['id'] == item['id'])
    selected = {**provenance, 'documents': [paper]}
    selected_bytes = canonical_bytes(selected)
    authors = ', '.join(paper['authors'])
    copyright_notice = ('<p>' + escape(paper['copyright_notice']) + '</p>') if paper['copyright_notice'] else ''
    footer = (
        '<footer data-legacy-attribution aria-label="Paper attribution">'
        '<h2>论文许可与改编说明 / Paper license and adaptation notice</h2>'
        '<p>' + escape(paper['title']) + ' — ' + escape(authors) + ' (' + str(paper['year']) + '). '
        '<a href="' + escape(paper['record_url'], quote=True) + '">' + escape(paper['arxiv_id']) + '</a>. '
        '<a rel="license" href="' + escape(paper['license_url'], quote=True) + '">CC BY 4.0</a>.</p>'
        + copyright_notice + '<p>' + escape(' '.join(paper['adaptations'])) + '</p>'
        '<p>Unofficial adaptation; no author endorsement. Individual translator, generation method '
        'and human review are not recorded.</p>'
        '<details><summary>Attribution and adaptation notice</summary><pre>'
        + escape(notice.decode('utf-8')) + '</pre></details>'
        '<details><summary>CC BY 4.0 — full license</summary><pre>'
        + escape(license_text.decode('utf-8')) + '</pre></details>'
        '<details><summary>Source and adaptation provenance</summary><pre>'
        + escape(json.dumps(selected, ensure_ascii=False, indent=2)) + '</pre></details></footer>'
    ).encode('utf-8')
    require(page.count(b'</body>') == 1, 'LEGACY_NAVIGATION_MISMATCH')
    return page.replace(b'</body>', footer + b'</body>', 1), {
        'legal/CC-BY-4.0.txt': license_text,
        'legal/legacy-NOTICE.md': notice,
        'legal/legacy-provenance.json': selected_bytes,
        'legal/legacy-manifest.json': release_bytes,
    }
