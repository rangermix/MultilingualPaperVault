from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
import pytest

from packages.ir import validate_source
from packages.parsers.inspect import PDFError, inspect_pdf
from packages.parsers.source_adapter import SourceAdapter
from packages.parsers.vlm_output import oxr_items


PAGE = {'page': 1, 'page_size': [600, 800]}


def test_oxr_single_fenced_listing_keeps_code_and_pdf_extent():
    diagnostics = []
    row, = oxr_items('```python\n    print(42)\n```', PAGE, diagnostics)

    child, = row['_semantic']['children']
    assert child['kind'] == 'code'
    assert child['text'] == '    print(42)\n'
    assert child['attrs']['code_language'] == 'python'
    assert row['prov'] == [{'page_no': 1, 'bbox': {'l': 0, 't': 0, 'r': 600, 'b': 800,
                                                 'coord_origin': 'TOPLEFT'}}]
    assert not row.get('_model_provenance')
    assert diagnostics[0]['code'] == 'PAGE_EXTENT_PROVENANCE'


def test_oxr_blank_page_and_invalid_completion():
    assert oxr_items(' \r\n', PAGE) == []
    with pytest.raises(PDFError, match='PARSER_OUTPUT_INVALID'):
        oxr_items({'content': 'not the completion string'}, PAGE)


def test_oxr_page_extent_preserves_heading_free_structure_through_source_recovery(tmp_path):
    pdf = tmp_path / 'input.pdf'
    writer = PdfWriter()
    writer.add_blank_page(width=600, height=800)
    writer.write(pdf)
    inspection = inspect_pdf(pdf)
    page = inspection['pages'][0]
    raw = 'A **measured** result.\n\n- First observation\n- Second observation\n\n```python\nprint(42)\n```'

    output = tmp_path / 'source'
    source = SourceAdapter().adapt(oxr_items(raw, page), inspection, pdf, 'original', output,
                                   model_generated_source=True, semantic=True)['source_revision']
    validate_source(source, asset_root=output)
    blocks = source['blocks']
    title = next(block for block in blocks if block['id'] == source['title_block_id'])
    assert title['normalized_text'] == ''
    paragraph = next(block for block in blocks if block['normalized_text'] == 'A measured result.')
    assert any(span.get('marks') == ['strong'] for span in paragraph['source_inline'])
    by_id = {block['id']: block for block in blocks}
    list_items = [block for block in blocks if block['kind'] == 'list_item']
    assert [[by_id[child]['normalized_text'] for child in item['attributes']['children_block_ids']]
            for item in list_items] == [['First observation'], ['Second observation']]
    code = next(block for block in blocks if block['kind'] == 'code')
    assert code['normalized_text'] == 'print(42)\n'
    assert paragraph['provenance'][0]['bbox'] == code['provenance'][0]['bbox'] == [0, 0, 600, 800]
    assert paragraph['provenance'][0]['geometry'] == code['provenance'][0]['geometry'] == 'inherited'
    assert code['attributes']['comparison_asset_id'] == 'page-image-1'
    assert code['attributes']['comparison_scope'] == code['attributes']['asset_scope'] == 'page'


def test_oxr_scanned_page_keeps_prose_and_code(tmp_path):
    pdf = tmp_path / 'scan.pdf'
    prose = 'The scan contains text before the code listing.'
    with Image.new('RGB', (600, 800), 'white') as image:
        drawing = ImageDraw.Draw(image)
        drawing.text((40, 70), prose, fill='black')
        drawing.text((40, 110), 'print(42)', fill='black')
        image.save(pdf, 'PDF', resolution=72)
    inspection = inspect_pdf(pdf)
    page = inspection['pages'][0]
    assert page['scan_suspected']
    assert page['image_regions'] == [{'bbox': [0, 0, 600, 800]}]

    output = tmp_path / 'source'
    rows = oxr_items(f'{prose}\n\n```python\nprint(42)\n```', page)
    result = SourceAdapter().adapt(rows, inspection, pdf, 'original', output,
                                   model_generated_source=True, semantic=True)
    source = result['source_revision']
    validate_source(source, asset_root=output)
    assert any(block['kind'] == 'paragraph' and block['normalized_text'] == prose for block in source['blocks'])
    assert any(block['kind'] == 'code' and block['normalized_text'] == 'print(42)\n' for block in source['blocks'])


def test_oxr_page_groups_keep_separate_provenance_during_native_continuation(tmp_path):
    pdf = tmp_path / 'continuation.pdf'
    completions = ['We establish', 'a baseline with a large model.']
    writer = PdfWriter()
    for text, baseline in zip(completions, (40, 750)):
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject({NameObject('/F1'): font}),
        })
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 40 {baseline} Td ({text}) Tj ET'.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    writer.write(pdf)
    inspection = inspect_pdf(pdf)
    rows = [row for text, page in zip(completions, inspection['pages']) for row in oxr_items(text, page)]

    output = tmp_path / 'source'
    result = SourceAdapter().adapt(rows, inspection, pdf, 'original', output,
                                   model_generated_source=True, semantic=True)
    source = result['source_revision']
    validate_source(source, asset_root=output)
    paragraphs = [block for block in source['blocks'] if block['kind'] == 'paragraph']
    assert [block['normalized_text'] for block in paragraphs] == completions
    assert [[locator['page'] for locator in block['provenance']] for block in paragraphs] == [[1], [2]]
