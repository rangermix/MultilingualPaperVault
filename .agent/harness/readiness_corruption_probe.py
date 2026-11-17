"""Fresh acceptance only: corruption fails explicit verification, not health polling."""

if __package__:
    from ._project import ROOT, artifact_path, output_path
else:
    from _project import ROOT, artifact_path, output_path
import hashlib
import json
from pathlib import Path
import stat

from packages.domain.config import Config
from packages.domain.db import Database
from packages.domain.errors import DomainError
from packages.domain.models import Document, SourceAsset
from packages.maintenance.__main__ import verify_data
from packages.storage import safe_path
from smoke_library import request

BASE='http://127.0.0.1:8080'


def main():
    state=json.loads(Path('/evidence/offline-library.json').read_text())
    cfg=Config.load();db=Database(cfg)
    with db.transaction() as session:
        document=session.get(Document,state['document_id'])
        assert document.title=='Offline acceptance'
        asset=session.get(SourceAsset,document.source_asset_id)
        path=safe_path(cfg.data,asset.storage_key,must_exist=True)
        assert cfg.data.resolve()==Path('/data')
    original=path.read_bytes();mode=stat.S_IMODE(path.stat().st_mode)
    assert hashlib.sha256(original).hexdigest()==state['original_sha256']
    request(BASE,'GET','/health/ready')
    verify_data(db,cfg)
    try:
        path.chmod(mode|stat.S_IWUSR)
        path.write_bytes(b'BROKEN'+original[6:])
        ready,_=request(BASE,'GET','/health/ready')
        assert ready['storage_integrity']=='not_checked' and ready['verified_objects'] is None,ready
        try:
            verify_data(db,cfg)
        except DomainError as failure:
            assert failure.code=='SOURCE_ASSET_CORRUPT',failure.code
        else:
            raise AssertionError('Explicit verification accepted a corrupt referenced PDF')
    finally:
        try:
            path.write_bytes(original)
        finally:
            path.chmod(mode)
    request(BASE,'GET','/health/ready')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==state['original_sha256']
    restored=verify_data(db,cfg)
    result={'status':'passed','scope':'fresh acceptance instance only','corrupt_pdf_readiness':200,
            'storage_integrity':'not_checked','explicit_verification_error':'SOURCE_ASSET_CORRUPT',
            'restored_readiness':200,'restored_verification':restored['status'],'original_bytes_restored':True}
    Path('/evidence/readiness-corruption.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':main()
