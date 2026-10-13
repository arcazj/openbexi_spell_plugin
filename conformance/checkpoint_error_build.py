"""Recompile one checked original frame-manager unit in an isolated graph."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile
from incremental_native import rebuild
import checkpoint_error_patches as patch

output=Path('/checkpoint-error-patch')
output.mkdir()
archive=Path('/input/SPELL2.6.10-src.zip')
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
with zipfile.ZipFile(archive) as bundle:
    original=bundle.read(patch.SOURCE)
path=Path('/source')/patch.SOURCE
ported=path.read_bytes()
mode=os.environ['CHECKPOINT_PATCH_MODE']
assert mode in ('audit','fix')
patched=patch.apply(patch.SOURCE,original,ported,audit=mode=='audit',fix=mode=='fix')
sources={}
for label,raw in [('original',original),('ported',ported),('patched',patched)]:
    target=output/label/patch.SOURCE
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(raw)
    sources[label+'_sha256']=hashlib.sha256(raw).hexdigest()
path.write_bytes(patched)
for name in ('checkpoint_error_patches.py','checkpoint_error_build.py','incremental_native.py'):
    shutil.copyfile(Path(__file__).parent/name,output/name)
result=rebuild([patch.SOURCE],output/'compiled')
report=dict(mode=mode,source=patch.SOURCE,sources=sources,
    recipes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.py')},
    artifacts={name:row['sha256'] for name,row in result['artifacts'].items()},
    original_artifacts={name:row['original_sha256'] for name,row in result['artifacts'].items()},
    limitation='Diagnostic native overlay; installed RECORD and original package manifest intentionally unchanged. Not distribution acceptance.')
(output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
