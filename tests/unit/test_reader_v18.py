"""Source Han Sans is the default in publication and offline exports."""

import zipfile

import pytest
from lxml import html

from packages.editorial.drafts import render_input
from packages.publisher import Publisher, export_bundle, export_single_html
from packages.publisher.renderer import render_html
from packages.templates import get_template
from test_reader_i18n_v16 import notice_fixture


@pytest.mark.parametrize(('version', 'locale', 'label'), [
    ('3.0', 'en', 'Source Han Sans'),
    ('4.0', 'zh-Hans', '思源黑体'),
])
def test_reader_default_changes_font_and_preserves_document(tmp_path, version, locale, label):
    previous = notice_fixture(tmp_path, locale, version)
    document = previous['document']['id']
    source, translation = previous['source_revision'], previous['translation_revision']
    current = render_input(document, source, translation)
    earlier = render_input(document, source, translation, 'reader-v17')
    assert current['render']['template_id'] == 'reader-v18'
    paths = {asset['id']: asset['storage_key'] for asset in source['assets']}
    rendered = html.fromstring(render_html(current, paths, include_source=True))
    old = html.fromstring(render_html(earlier, paths, include_source=True))
    assert rendered.xpath('//select[@data-font-select]/option[1]/text()') == [label]
    assert rendered.xpath('//select[@data-font-select]/option[1]/@value') == ['default']
    assert rendered.xpath('//select[@data-font-select]/option[@value="misans" or @value="source-han-sans"]') == []
    assert 'Copyright 2014-2025 Adobe' in rendered.xpath('string(//footer[@class="reader-font-notice"])')
    assert html.tostring(rendered.xpath('//article')[0]) == html.tostring(old.xpath('//article')[0])


def test_offline_formats_embed_default_and_code_fonts_with_notices(tmp_path):
    previous = notice_fixture(tmp_path, 'en', '4.0')
    current = render_input(previous['document']['id'], previous['source_revision'], previous['translation_revision'])
    artifact = tmp_path / 'reader-v18'
    manifest = Publisher().build(current, tmp_path, artifact, include_source=True)
    font = next(entry for entry in manifest['files'] if entry['path'] == 'fonts/SourceHanSansCN-VF.ttf.woff2')
    assert font['media_type'] == 'font/woff2' and font['byte_size'] == 7711988
    css = (artifact / 'reader.css').read_text('utf-8')
    assert '--reader-font: "Source Han Sans CN"' in css
    assert 'MiSans' not in css
    assert len([entry for entry in manifest['files'] if entry['media_type'] == 'font/woff2']) == 5
    math = next(entry for entry in manifest['files'] if entry['path'] == 'math.js')
    assert math['sha256'] == 'fa140498b8cfc8302cbe5e7cb1bdbc1f952bc38b3fa258ede09e73edbf9a74bc'
    old_math = next(entry for entry in get_template('reader-v17')['extra_assets'] if entry['path'] == 'math.js')
    assert old_math['sha256'] == '10a91b479cd927446ceb60409fb0d72b5d0d05eaf446c9e52fafd64058c84540'

    single = export_single_html(artifact, tmp_path / 'reader.html').read_bytes()
    bundle = export_bundle(artifact, tmp_path / 'reader.zip')
    with zipfile.ZipFile(bundle) as archive:
        assert archive.read('reader.css').count(b'data:font/woff2;base64,') == 5
        assert b'Copyright 2014-2025 Adobe' in archive.read('fonts/SourceHanSans-OFL.txt')
        assert b'data-online-reader' not in archive.read('index.html')
    assert single.count(b'data:font/woff2;base64,') == 5
    assert b'Copyright 2014-2025 Adobe' in single
    assert b'<nav class="reader-return" data-online-reader' not in single
