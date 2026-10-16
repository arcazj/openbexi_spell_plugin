"""Compile the checked two-unit PROC correction as an explicit diagnostic overlay."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'source_port'),str(ROOT/'distribution')]
import proc_dictionary_patches as patch
from incremental_native import rebuild

output=Path('/proc-dictionary-patch');output.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources={}
with zipfile.ZipFile(ROOT/'docs/reference/SPELL2.6.10-src.zip') as archive:
    for name in patch.PREIMAGES:
        source=Path('/source')/name
        original=archive.read(name);ported=source.read_bytes()
        patched=patch.apply(name,original,ported)
        sources[name]={}
        for label,content in (('original',original),('ported',ported),('patched',patched)):
            target=output/label/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
            sources[name][label+'_sha256']=sha(target)
        source.write_bytes(patched)
compiled=rebuild(list(patch.PREIMAGES),output/'compiled')
assert set(compiled['artifacts'])=={'libspell_executor313.so'}
recipes={}
for relative in ('source_port/proc_dictionary_patches.py','conformance/proc_dictionary_build.py',
                 'distribution/incremental_native.py'):
    target=output/Path(relative).name;shutil.copyfile(ROOT/relative,target);recipes[target.name]=sha(target)
report=dict(passed=True,scope='Compiled diagnostic correction; behavioral acceptance remains required',
    sources=sources,recipes=recipes,
    artifacts={name:row['sha256'] for name,row in compiled['artifacts'].items()},
    original_artifacts={name:row['original_sha256'] for name,row in compiled['artifacts'].items()},
    incremental_build_sha256=sha(output/'compiled/incremental-build.json'),
    full_release_accepted=False)
(output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
