"""Retain original/preimage/source and independently relink only scheduler units."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
import scheduler_patches
from incremental_native import rebuild

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
output=Path('/scheduler-native-patch')
output.mkdir()
archive=Path('/input/SPELL2.6.10-src.zip')
assert sha(archive)=='2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
records={}
with zipfile.ZipFile(archive) as bundle:
    for name in scheduler_patches.PREIMAGES:
        source=Path('/source',name)
        original,ported=bundle.read(name),source.read_bytes()
        patched=scheduler_patches.apply(name,original,ported)
        records[name]={}
        for label,content in (('original',original),('ported',ported),('patched',patched)):
            path=output/label/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(content)
            records[name][label]=sha(path)
        source.write_bytes(patched)
for name in ('scheduler_patches.py','scheduler_native_build.py','incremental_native.py'):
    shutil.copyfile(Path(__file__).parent/name,output/name)
for name in ('integrated-native','integrated-python'):
    shutil.copytree(Path('/out',name),output/('base-'+name))
try:result=rebuild(list(scheduler_patches.PREIMAGES),output/'compiled')
except Exception:
    for log in (output/'compiled').glob('*.log'):print(log.name,log.read_text()[-10000:])
    raise
(output/'runtime-bin').mkdir()
for name in ('SPELL-ExecutorCmd_v3','SPELL-Listener','SPELL-Executor_v3','SPELL-Context','SPELL-Service_v3','libspell_executor313.so'):
    source=output/'compiled'/name
    if not source.exists():source=Path('/out',name)
    shutil.copyfile(source,output/'runtime-bin'/name)
manifest=dict(archive_sha256=sha(archive),source_hashes=records,
    compiler_image='sha256:dc15d9f1f6de3ab00a8a90bc70c0bd2a7bab473b0e18202ea1df087d1085b471',
    runtime_base='sha256:627f1b3a529e3581618dc739a4f0029c11e29f8ca654a58b284076f9214db708',
    recipes={p.name:sha(p) for p in output.glob('*.py')},
    artifacts={p.name:sha(p) for p in (output/'runtime-bin').iterdir()},
    inherited_composition={name:sha(output/name/'manifest.json') for name in ('base-integrated-native','base-integrated-python')},
    profile='Isolated scheduler candidate derived from exact97f9a6 integrated diagnostic; newer IPC/TIME/Verify Python/native sources retained together. No full release acceptance.')
(output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
