"""Materialize a traceable original-source patch for development qualification."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source_port'))
from patches import apply


def main():
    archive = ROOT/'docs/reference/SPELL2.6.10-src.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
    output = ROOT/'.qualification/v0.5/time-port'
    output.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        original = bundle.read('src/spell/spell/lib/adapter/utctime.py')
    patched = apply('spell/lib/adapter/utctime.py',original)
    compile(patched,'utctime.py','exec')
    (output/'utctime.original.py').write_bytes(original)
    (output/'utctime.py').write_bytes(patched)
    shutil.copyfile(ROOT/'source_port/patches.py',output/'patches.py')
    report = {'profile':'development TIME conformance overlay; not a distribution release',
              'files':{name:hashlib.sha256((output/name).read_bytes()).hexdigest()
                       for name in ('utctime.original.py','utctime.py','patches.py')}}
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
