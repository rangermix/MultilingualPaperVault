from pathlib import Path
import json
import re
import zipfile
import pytest
from sqlalchemy import select,func
from packages.domain.models import Document,Artifact,SourceRevision,TranslationRevision,ReviewRecord,SourceAsset,Edition,Publication
from packages.ir import canonical_bytes,digest
from packages.seed.legacy import seed_legacy,checked_release,omitted_adaptations
from packages.publisher import verify_artifact,export_bundle,export_single_html

pytestmark=pytest.mark.postgres
ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def included_seed_bundle():
    manifest = checked_release(allow_omitted_adaptations=True)
    if omitted_adaptations(manifest):
        pytest.skip('This source snapshot omits the original bilingual seed adaptations.')
    return manifest


@pytest.mark.parametrize('include_source', [False, True])
def test_known_legacy_seed_is_idempotent_and_not_fake_ir(included_seed_bundle,database,tmp_path,include_source):
    db,cfg=database
    first=seed_legacy(db,cfg)
    frozen_files={str(path.relative_to(cfg.data)):path.read_bytes() for path in cfg.data.rglob('*') if path.is_file()}
    second=seed_legacy(db,cfg)
    assert first['created']==2 and second['created']==0
    assert frozen_files=={str(path.relative_to(cfg.data)):path.read_bytes() for path in cfg.data.rglob('*') if path.is_file()}
    with db.transaction() as session:
        assert session.scalar(select(func.count()).select_from(Document))==2
        assert session.scalar(select(func.count()).select_from(SourceRevision))==0
        assert session.scalar(select(func.count()).select_from(TranslationRevision))==0
        assert session.scalar(select(func.count()).select_from(ReviewRecord))==0
        artifacts=session.scalars(select(Artifact)).all()
    for artifact in artifacts:
        root=cfg.data/artifact.storage_key;manifest=verify_artifact(root)
        frozen=(ROOT/'res'/manifest['legacy_source_path']).read_bytes()
        assert (root/'legacy-original.html').read_bytes()==frozen
        expected=frozen.replace(b'<a href="../index.html">',b'<a href="/">',1)
        page=(root/'index.html').read_bytes()
        assert re.sub(rb'<footer data-legacy-attribution\b.*?</footer>',b'',page,flags=re.S)==expected
        assert re.search(rb'<style>(.*?)</style>',expected,re.S).group(1)==re.search(rb'<style>(.*?)</style>',frozen,re.S).group(1)
        assert artifact.id.endswith('-artifact-v2') and manifest['renderer_version']=='legacy-copy-v2'
        output=export_single_html(root,tmp_path/(artifact.id+'.html'),include_source=include_source).read_text('utf-8')
        assert 'data:image/png;base64,' in output and 'href="/"' not in output and 'href="source/' not in output
        assert ('data:application/pdf;base64,' in output)==include_source
        assert 'data-legacy-attribution' in output and 'https://creativecommons.org/licenses/by/4.0/' in output
        assert 'Creative Commons Attribution 4.0 International Public License' in output
        assert 'Individual translator, generation method' in output and 'arxiv_id' in output
        bundle=export_bundle(root,tmp_path/(artifact.id+'.zip'),include_source=include_source)
        with zipfile.ZipFile(bundle) as archive:
            assert any(name.endswith('.pdf') for name in archive.namelist())==include_source
            assert 'legacy-original.html' not in archive.namelist()
            assert archive.read('legal/CC-BY-4.0.txt')==(ROOT/'res/reference/CC-BY-4.0.txt').read_bytes()
            assert archive.read('legal/legacy-NOTICE.md')==(ROOT/'res/reference/legacy-NOTICE.md').read_bytes()
            assert archive.read('legal/legacy-manifest.json')==(ROOT/'res/reference/legacy-manifest.json').read_bytes()
            provenance=json.loads(archive.read('legal/legacy-provenance.json'))
            assert [paper['id'] for paper in provenance['documents']]==[artifact.document_id]
            assert b'data-legacy-attribution' in archive.read('index.html')
            for href in re.findall(r'\[[^\]]*\]\(([^)]+)\)',archive.read('legal/legacy-NOTICE.md').decode('utf-8')):
                assert href.startswith(('https:', 'http:')) or 'legal/'+href in archive.namelist()
        assert frozen_files=={str(path.relative_to(cfg.data)):path.read_bytes() for path in cfg.data.rglob('*') if path.is_file()}


def test_existing_v1_seed_keeps_its_artifact_pointer_and_bytes(included_seed_bundle,database):
    db,cfg=database
    seed=included_seed_bundle['documents'][0]
    document_id=seed['id'];edition_id=document_id+'-zh-Hans';aid=document_id+'-artifact-v1'
    key=f'documents/{document_id}/artifacts/{aid}';root=cfg.data/key
    files={row['output']:(ROOT/'res'/row['path']).read_bytes() for row in seed['files']}
    files['index.html']=files['legacy-original.html'].replace(b'<a href="../index.html">',b'<a href="/">',1)
    files['reader.css']=(ROOT/'res/reference/reader-v1.css').read_bytes()
    manifest={'schema_version':'1.0','legacy':True,'renderer_version':'legacy-copy-v1',
              'files':[{'path':name,'byte_size':len(content),'sha256':digest(content)} for name,content in sorted(files.items())]}
    manifest['content_digest']=digest(manifest['files'])
    files['manifest.json']=canonical_bytes(manifest)
    for name,content in files.items():
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    source=files[seed['source_output']]
    with db.transaction() as session:
        session.add(SourceAsset(id='old-seed-source',sha256=digest(source),byte_size=len(source),
                                page_count=seed['page_count'],storage_key=key+'/'+seed['source_output']))
        session.flush()
        session.add(Document(id=document_id,title='Existing seed title',source_asset_id='old-seed-source',status='published',generation=7))
        session.flush()
        session.add(Edition(id=edition_id,document_id=document_id,target_locale='zh-Hans',generation=9,current_artifact_id=aid))
        session.flush()
        session.add(Artifact(id=aid,document_id=document_id,edition_id=edition_id,template_id='reader-v1',
                             storage_key=key,manifest_hash=digest(manifest),state='verified',legacy=True))
        session.add(Publication(id='old-seed-publication',edition_id=edition_id,artifact_id=aid,generation=9,operation='seed_legacy',origin='migration'))
    result=seed_legacy(db,cfg)
    assert result['created']==1
    assert {'document_id':document_id,'status':'already_seeded'} in result['documents']
    assert files=={str(path.relative_to(root)).replace('\\','/'):path.read_bytes() for path in root.rglob('*') if path.is_file()}
    assert not (root.parent/(document_id+'-artifact-v2')).exists()
    with db.transaction() as session:
        assert session.get(Document,document_id).title=='Existing seed title'
        assert session.get(Document,document_id).generation==7
        edition=session.get(Edition,edition_id)
        assert edition.current_artifact_id==aid and edition.generation==9
        assert session.get(Artifact,aid).manifest_hash==digest(manifest)
        assert session.scalar(select(func.count()).select_from(Publication).where(Publication.edition_id==edition_id))==1
