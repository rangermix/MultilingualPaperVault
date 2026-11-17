"""Reader v18 typography around the frozen v17 bilingual document renderer."""

from packages.paths import ROOT
from .reader_locales_v17 import resolve_reader_locale, translate
from .reader_v17 import esc, render_html as render_v17

RENDERER_VERSION = 'reader-python-18.0.0'


def render_html(ir, asset_paths, *, include_source=False):
    locale = resolve_reader_locale(ir['translation_revision']['target_language'])

    def text(key, **values):
        return esc(translate(locale, key, **values))

    output = render_v17(ir, asset_paths, include_source=include_source).decode('utf-8')
    label = text('思源黑体')
    old_hint = text('使用系统默认字体；其他选项使用本机字体。')
    hint = text('{font} · 已内置，可离线使用。', font=translate(locale, '思源黑体'))
    # Only the authored font control and footer are changed. Paper text and its
    # HTML, anchors, and localized evidence are the frozen renderer's output.
    output = output.replace(f'<select data-font-select title="{old_hint}">',
                            f'<select data-font-select title="{hint}">', 1)
    output = output.replace(f'<option value="default">{text("默认（系统字体）")}</option>',
                            f'<option value="default">{label}</option>', 1)
    output = output.replace(f'<option value="source-han-sans">{label}</option>', '', 1)
    license_text = (ROOT / 'res/vendor/reader-fonts/SourceHanSans-OFL.txt').read_text('utf-8')
    notice = f'<details><summary>{text("{font} 字体许可", font="Source Han Sans")}</summary><pre>{esc(license_text)}</pre></details>'
    output = output.replace('</footer>', notice + '</footer>', 1)
    return output.encode('utf-8')
