"""Authored stand-ins for archived reader assets in read and export tests."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from packages.ir import digest
from packages.paths import ROOT
from packages.publisher import Publisher, reader_v13, reader_v15, reader_v16
from packages.templates import registry


RETIRED_FONT_NOTICE = "Synthetic notice for the archived reader font fixture."
_FONT_FILES = {
    'MiSans-Regular.woff2': 'JetBrainsMono-Regular.woff2',
    'MiSans-Bold.woff2': 'JetBrainsMono-Bold.woff2',
}


@contextmanager
def historical_reader_resources(root):
    """Let frozen renderer tests exercise their license markup."""
    fonts = root / 'res/vendor/reader-fonts'
    fonts.mkdir(parents=True, exist_ok=True)
    shipped_fonts = ROOT / 'res/vendor/reader-fonts'
    (fonts / 'MiSans-LICENSE.txt').write_text(RETIRED_FONT_NOTICE, encoding='utf-8')
    (fonts / 'JetBrainsMono-OFL.txt').write_bytes((shipped_fonts / 'JetBrainsMono-OFL.txt').read_bytes())
    for archived, substitute in _FONT_FILES.items():
        (fonts / archived).write_bytes((shipped_fonts / substitute).read_bytes())

    with (patch.object(reader_v13, 'ROOT', root), patch.object(reader_v15, 'ROOT', root),
          patch.object(reader_v16, 'ROOT', root)):
        yield fonts


def build_historical_reader(ir, asset_root, output, *, include_source):
    """Create a fixture with the archived layout and same-origin asset paths."""
    template_id = ir['render']['template_id']
    template = registry.get_template(template_id)
    assert template['available_for_build'] is False
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='historical-reader-', dir=output.parent) as scratch:
        with historical_reader_resources(Path(scratch)) as fonts:
            assets = []
            for entry in template['extra_assets']:
                if entry['path'].startswith('fonts/MiSans'):
                    source = fonts / entry['path'].split('/')[-1]
                    entry = {**entry, 'source': source.resolve(), 'sha256': digest(source.read_bytes())}
                assets.append(entry)
            fixture_template = {**template, 'available_for_build': True, 'extra_assets': assets}
            with patch.object(registry, 'get_template', return_value=fixture_template):
                return Publisher().build(ir, asset_root, output, include_source=include_source)
