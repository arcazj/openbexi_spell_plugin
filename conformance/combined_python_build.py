"""Retain and apply checked FLOW Python validation in the combined runtime."""
import hashlib
import json
from pathlib import Path
import shutil
import sysconfig

import flow_patches

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
root = Path(__file__).resolve().parent
output = root / 'python'
output.mkdir()
site = Path(sysconfig.get_path('purelib'))
name = 'spell/lang/helpers/exechelper.py'
source = site / name
original = output / 'original' / name
original.parent.mkdir(parents=True)
shutil.copyfile(source, original)
changes = flow_patches.apply_python_tree(site, output / 'source-patches.json')
compile(source.read_bytes(), str(source), 'exec')
patched = output / 'patched' / name
patched.parent.mkdir(parents=True)
shutil.copyfile(source, patched)
manifest = {'changes': changes, 'original_sha256': sha(original), 'patched_sha256': sha(patched),
            'recipes': {'combined_python_build.py': sha(Path(__file__)),
                        'flow_patches.py': sha(root / 'flow_patches.py')},
            'native_manifest_sha256': sha(root / 'manifest.json'),
            'profile': 'Native FLOW public argument validation; behavior qualification remains separate'}
(output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
