"""Materialize original-source policy and TIME patches for native qualification."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source_port'))
from patches import apply

FILES = ('spell/lib/adapter/utctime.py', 'spell/lang/helpers/basehelper.py',
         'spell/lang/helpers/genhelper.py', 'spell/config/contexts.py')


def main():
    archive = ROOT/'docs/reference/SPELL2.6.10-src.zip'
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert digest == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
    output = ROOT/'.qualification/v0.5/common-port'
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    with zipfile.ZipFile(archive) as bundle:
        for name in FILES:
            original = bundle.read('src/spell/' + name)
            patched = apply(name, original)
            compile(patched, name, 'exec')
            for prefix, content in (('original', original), ('patched', patched)):
                path = output/prefix/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                records[prefix+'/'+name] = hashlib.sha256(content).hexdigest()
    shutil.copyfile(ROOT/'source_port/patches.py', output/'patches.py')
    records['patches.py'] = hashlib.sha256((output/'patches.py').read_bytes()).hexdigest()
    manifest = {'profile': 'development COMMON/TIME conformance overlay; not a distribution release',
                'archive_sha256': digest, 'files': records}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
