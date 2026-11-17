"""New readers omit MiSans while historical publication contracts remain usable."""
from copy import deepcopy
import json
from pathlib import Path
import zipfile

import pytest
from lxml import html

from packages.domain.errors import DomainError
from packages.editorial.drafts import render_input
from packages.ir import digest
from packages.paths import ROOT
from packages.publisher import Publisher, export_bundle, export_single_html, verify_artifact
from packages.publisher.reader_locales_v17 import MESSAGES, SUPPORTED_READER_LOCALES
from packages.publisher.renderer import render_html
from packages.publisher.reader_v17 import RENDERER_VERSION
from packages.templates.registry import get_template
from tests.historical_readers import RETIRED_FONT_NOTICE, build_historical_reader
from test_reader_i18n_v16 import notice_fixture


pytestmark = pytest.mark.usefixtures('archived_reader_assets')


def current_fixture(tmp_path, locale='ja', version='4.0'):
    previous = notice_fixture(tmp_path, locale, version)
    return render_input(previous['document']['id'], previous['source_revision'],
                        previous['translation_revision'], 'reader-v17')


@pytest.mark.parametrize('version', ['3.0', '4.0'])
@pytest.mark.parametrize('locale', SUPPORTED_READER_LOCALES)
def test_current_reader_omits_misans_without_changing_paper(tmp_path, version, locale):
    ir = current_fixture(tmp_path, locale, version)
    before = deepcopy(ir)
    paths = {asset['id']: asset['storage_key'] for asset in ir['source_revision']['assets']}
    output = render_html(ir, paths, include_source=True)
    tree = html.fromstring(output)
    old = render_input(ir['document']['id'], ir['source_revision'], ir['translation_revision'], 'reader-v16')
    historical = html.fromstring(render_html(old, paths, include_source=True))

    assert tree.get('lang') == locale
    assert 'misans' not in output.decode('utf-8').casefold()
    assert 'misans' not in tree.xpath('//select[@data-font-select]/option/@value')
    assert tree.xpath('//select[@data-font-select]/option[@value="default"]')
    assert tree.xpath('//select[@data-code-font-select]/option[@value="default"]')
    # The typography change must preserve source/translation text, rich content,
    # stable block anchors and parser notices rather than rebuilding content.
    for selector in ('//*[@data-language]', '//article', '//details[@class="block-notes"]'):
        assert [html.tostring(node) for node in tree.xpath(selector)] == [
            html.tostring(node) for node in historical.xpath(selector)]
    assert tree.xpath('//*[@data-block-id]/@id') == historical.xpath('//*[@data-block-id]/@id')
    assert ir == before


def test_current_template_bundles_only_ofl_code_fonts_and_new_catalog_is_clean():
    current, historical = get_template('reader-v17'), get_template('reader-v16')
    assert current['id'] != historical['id']
    assert current['renderer_version'] == RENDERER_VERSION == 'reader-python-17.0.0'
    assert not any('misans' in asset['path'].casefold() for asset in current['extra_assets'])
    assert any('MiSans' in asset['path'] for asset in historical['extra_assets'])
    assert historical['available_for_build'] is False
    fonts = [asset for asset in current['extra_assets'] if asset['media_type'] == 'font/woff2']
    assert {Path(asset['path']).name for asset in fonts} == {
        'JetBrainsMono-Regular.woff2', 'JetBrainsMono-Italic.woff2',
        'JetBrainsMono-Bold.woff2', 'JetBrainsMono-BoldItalic.woff2'}
    assert any(asset['path'].endswith('JetBrainsMono-OFL.txt') for asset in current['extra_assets'])
    assert 'misans' not in (ROOT / current['css_path']).read_text('utf-8').casefold()
    assert 'misans' not in json.dumps(MESSAGES, ensure_ascii=False).casefold()
    assert set(MESSAGES) == set(SUPPORTED_READER_LOCALES)


def test_font_option_removal_preserves_literal_paper_and_evidence_text(tmp_path):
    from test_reader_sidenotes import refresh, set_inline
    ir = current_fixture(tmp_path, version='3.0')
    literal = 'This paper evaluates MiSans as source material.'
    set_inline(ir, 'p1', [{'type': 'text', 'text': literal}])
    block = next(block for block in ir['source_revision']['blocks'] if block['id'] == 'p1')
    block['warnings'] = ['Original MiSans evidence remains unchanged.']
    refresh(ir)
    before = deepcopy(ir)
    paths = {asset['id']: asset['storage_key'] for asset in ir['source_revision']['assets']}
    tree = html.fromstring(render_html(ir, paths))
    assert tree.get_element_by_id('b-p1').text_content().count(literal) == 2
    assert 'Original MiSans evidence remains unchanged.' in tree.text_content()
    assert not tree.xpath('//select[@data-font-select]/option[@value="misans"]')
    assert ir == before


@pytest.mark.parametrize('version', ['3.0', '4.0'])
@pytest.mark.parametrize('include_source', [False, True])
def test_current_exports_omit_misans_and_preserve_publication(tmp_path, version, include_source):
    ir = current_fixture(tmp_path, version=version)
    artifact = tmp_path / 'current-publication'
    asset_root = Path('tests') if version == '3.0' else tmp_path
    manifest = Publisher().build(ir, asset_root, artifact, include_source=True)
    before = {entry['path']: entry['sha256'] for entry in manifest['files']}
    assert manifest['template_id'] == 'reader-v17'
    assert not any('misans' in entry['path'].casefold() for entry in manifest['files'])
    assert len([entry for entry in manifest['files'] if entry['media_type'] == 'font/woff2']) == 4

    single = export_single_html(artifact, tmp_path / 'single.html', include_source=include_source)
    bundle = export_bundle(artifact, tmp_path / 'bundle.zip', include_source=include_source)
    with zipfile.ZipFile(bundle) as archive:
        assert not any('misans' in name.casefold() for name in archive.namelist())
        archive.extractall(tmp_path / 'bundle')
    exported = verify_artifact(tmp_path / 'bundle')
    assert exported['template_id'] == 'reader-v17'
    for path in (single, tmp_path / 'bundle/index.html', tmp_path / 'bundle/reader.css'):
        content = path.read_text('utf-8')
        assert 'misans' not in content.casefold()
        if path.suffix == '.html':
            tree = html.fromstring(content, parser=html.HTMLParser(huge_tree=True))
            assert tree.get('lang') == 'ja'
            assert not tree.xpath('//nav[@data-online-reader]')
            assert bool(tree.xpath('//a[@download]')) == include_source
    standalone = single.read_text('utf-8')
    assert 'SIL OPEN FONT LICENSE Version 1.1' in standalone
    assert 'data:font/woff2;base64,' in standalone
    assert all(digest((artifact / path).read_bytes()) == sha for path, sha in before.items())


def test_default_rich_reader_preserves_snapshots(tmp_path):
    ir = current_fixture(tmp_path)
    source, translation = deepcopy(ir['source_revision']), deepcopy(ir['translation_revision'])
    automatic = render_input(ir['document']['id'], source, translation)
    assert automatic['render']['template_id'] == 'reader-v18'
    assert automatic['source_revision'] == source == ir['source_revision']
    assert automatic['translation_revision'] == translation == ir['translation_revision']


def test_historical_reader_can_export_existing_publication(tmp_path):
    previous = notice_fixture(tmp_path, 'ja', '3.0')
    artifact = tmp_path / 'historical-publication'
    manifest = build_historical_reader(previous, Path('tests'), artifact, include_source=True)
    before = {entry['path']: entry['sha256'] for entry in manifest['files']}
    assert manifest['template_id'] == 'reader-v16'
    assert any('MiSans' in entry['path'] for entry in manifest['files'])
    current = render_input(previous['document']['id'], previous['source_revision'],
                           previous['translation_revision'], 'reader-v17')
    Publisher().build(current, Path('tests'), tmp_path / 'new-publication', include_source=True)
    exported = export_single_html(artifact, tmp_path / 'historical.html').read_text('utf-8')
    assert RETIRED_FONT_NOTICE in exported
    assert 'value="misans"' in exported
    assert verify_artifact(artifact)['template_id'] == 'reader-v16'
    assert all(digest((artifact / path).read_bytes()) == sha for path, sha in before.items())


def test_archived_template_cannot_generate_a_new_publication():
    for version in range(13, 17):
        template_id = f'reader-v{version}'
        with pytest.raises(DomainError) as issue:
            get_template(template_id, for_build=True)
        assert issue.value.code == 'TEMPLATE_RETIRED'


def test_v16_renderer_catalog_templates_remain_frozen():
    hashes = {
        'src/packages/publisher/reader_v16.py': 'dc92cf0ab122b8a9f79f7580d225d776d6fd3413dbeecda9f57def52948f6e4e',
        'src/packages/publisher/reader_locales_v16.py': 'c21aa5b2dd3bb9a44bf6fdf376a8a19b92f50f4eb657d25e23b5a916d195d836',
        'src/packages/templates/reader-v16.css': '33040019fbdea0846e2527bbd266fd4c1b387d9539e041d954b2a4c46bff6f69',
        'src/packages/templates/reader-v16.js': '883ac1e2db4fe09f2018ac72791c600471a9d53e73e0e1de17a2c9548ba26124',
    }
    for name, expected in hashes.items():
        content = (ROOT / name).read_bytes()
        assert digest(content.replace(b'\r\n', b'\n')) == expected
    assert not list((ROOT / 'res/vendor/reader-fonts').glob('MiSans-*'))
