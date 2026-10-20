"""Stage large release files as independently hashed, lossless numbered parts."""
import hashlib
import shutil


def stage_artifact(source, output, asset_limit=2*1024**3, part_size=1024**3):
    size=source.stat().st_size
    assert 0<part_size<asset_limit
    if size<asset_limit:
        target=output/source.name;shutil.copyfile(source,target)
        return [target],None
    parts=[];whole=hashlib.sha256();total=0
    with source.open('rb') as stream:
        for index in range((size+part_size-1)//part_size):
            target=output/(source.name+f'.part{index+1:03d}')
            remaining=min(part_size,size-total)
            with target.open('wb') as dest:
                while remaining:
                    block=stream.read(min(4*1024*1024,remaining));assert block
                    dest.write(block);whole.update(block);total+=len(block);remaining-=len(block)
            parts.append(target)
        assert not stream.read(1) and total==size
    return parts,dict(sha256=whole.hexdigest(),bytes=total,parts=[p.name for p in parts])


REASSEMBLE_SCRIPT='''"""Verify and join the numbered evidence parts from the v0.6 release."""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'RELEASE_MANIFEST.json').read_bytes())

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

for name,record in manifest['reassembled_artifacts'].items():
    assert Path(name).name==name and not Path(name).is_absolute()
    target=ROOT/name
    for part in record['parts']:
        assert Path(part).name==part and not Path(part).is_absolute()
        path=ROOT/part;expected=manifest['assets'][part]
        assert path.stat().st_size==expected['bytes'] and digest(path)==expected['sha256'],part
    if target.exists():
        assert target.stat().st_size==record['bytes'] and digest(target)==record['sha256'],name+' already exists with different contents'
        print('Already verified: '+name)
        continue
    h=hashlib.sha256();size=0
    with target.open('xb') as dest:
        for part in record['parts']:
            with (ROOT/part).open('rb') as source:
                for block in iter(lambda:source.read(4*1024*1024),b''):
                    dest.write(block);h.update(block);size+=len(block)
    assert h.hexdigest()==record['sha256'] and size==record['bytes'],name
    print('Reassembled and verified: '+name)
'''
