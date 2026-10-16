"""LRM p79: apply the existing read-only database view to mmd:// objects."""
# SPDX-License-Identifier: LGPL-3.0-or-later
import hashlib
import json
from pathlib import Path

PREIMAGES={'spell/lib/adapter/dbmgr.py':'012b987e033454acfa8001f81beaa39eb5dcb5b909e57e557991cadab892cf1e'}


def apply(name,raw):
    if hashlib.sha256(raw).hexdigest()!=PREIMAGES[name]:raise ValueError('Manoeuvre database preimage differs')
    old=b"        if dbName == 'SCDB':\n"
    if raw.count(old)!=1:raise ValueError('Read-only database selection anchor differs')
    result=raw.replace(old,b"        if dbName == 'SCDB' or dbName.startswith('mmd://'):\n")
    compile(result,name,'exec');return result


def apply_tree(site,evidence):
    site,evidence=Path(site),Path(evidence);manifest={}
    for name,before in PREIMAGES.items():
        raw=(site/name).read_bytes();result=apply(name,raw)
        for stage,data in (('original',raw),('patched',result)):
            path=evidence/stage/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        (site/name).write_bytes(result)
        manifest[name]=dict(preimage_sha256=before,sha256=hashlib.sha256(result).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':
    import sys
    apply_tree(sys.argv[1],sys.argv[2])
