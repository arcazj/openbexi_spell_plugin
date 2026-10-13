"""Recompile the separately checked frame unwind, source identity and context units."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from incremental_native import rebuild
import checkpoint_error_patches as frame_patch
import checkpoint_identity_patches as identity_patch
import checkpoint_context_patches as context_patch

output=Path('/checkpoint-identity-patch')
output.mkdir()
archive=Path('/input/SPELL2.6.10-src.zip')
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
sources={}
with zipfile.ZipFile(archive) as bundle:
    for patch in (frame_patch,identity_patch,context_patch):
        original=bundle.read(patch.SOURCE)
        path=Path('/source')/patch.SOURCE
        ported=path.read_bytes()
        patched=(patch.apply(patch.SOURCE,original,ported,fix=True) if patch is frame_patch
            else patch.apply(patch.SOURCE,original,ported))
        hashes={}
        for label,raw in [('original',original),('ported',ported),('patched',patched)]:
            target=output/label/patch.SOURCE
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(raw)
            hashes[label+'_sha256']=hashlib.sha256(raw).hexdigest()
        sources[patch.SOURCE]=hashes
        path.write_bytes(patched)
for name in ('checkpoint_error_patches.py','checkpoint_identity_patches.py','checkpoint_context_patches.py','checkpoint_identity_build.py','incremental_native.py'):
    shutil.copyfile(Path(__file__).parent/name,output/name)
result=rebuild(list(sources),output/'compiled')
report=dict(mode="identity",sources=sources,
    recipes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.py')},
    artifacts={name:row['sha256'] for name,row in result['artifacts'].items()},
    original_artifacts={name:row['original_sha256'] for name,row in result['artifacts'].items()},
    limitation='Diagnostic native overlay; installed RECORD and original package manifest intentionally unchanged. Not distribution acceptance.')
(output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
