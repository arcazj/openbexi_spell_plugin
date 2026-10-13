"""Materialize the checked DATA/FILES overlay, retaining originals and recipe."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source_port'))
from data_files_patches import PREIMAGES, apply


def main():
    archive = ROOT/'docs/reference/SPELL2.6.10-src.zip'
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert archive_hash == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
    output = ROOT/'.qualification/v0.5/data-files-port'
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    with zipfile.ZipFile(archive) as bundle:
        for name in PREIMAGES:
            original = bundle.read('src/spell/' + name)
            for prefix, content in [('original', original), ('patched', apply(name, original))]:
                path = output/prefix/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                records[prefix+'/'+name] = hashlib.sha256(content).hexdigest()
    shutil.copyfile(ROOT/'source_port/data_files_patches.py', output/'data_files_patches.py')
    records['data_files_patches.py'] = hashlib.sha256((output/'data_files_patches.py').read_bytes()).hexdigest()
    manifest = {'archive_sha256': archive_hash, 'files': records,
                'profile': 'Development DATA/FILES overlay; not a distribution release'}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
