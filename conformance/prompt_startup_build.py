"""Retain exact-source differential probes and compile the prompt transition correction."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'source_port'), str(ROOT / 'distribution')]
import prompt_startup_patches as patch
from incremental_native import rebuild

output = Path('/prompt-startup-patch')
output.mkdir()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
source = Path('/source') / patch.SOURCE
ported = source.read_bytes()
with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
    original = archive.read(patch.SOURCE)
patched = patch.apply(patch.SOURCE, original, ported)
for label, content in (('original', original), ('ported', ported), ('patched', patched)):
    (output / (label + '.C')).write_bytes(content)
subprocess.run([sys.executable, str(ROOT / 'conformance/prompt_startup_probe.py'),
                str(output / 'probes')], check=True)
probes = json.loads((output / 'probes/result.json').read_bytes())
assert probes['passed'] and probes['preimage_sha256'] == sha(output / 'ported.C')
assert probes['patched_sha256'] == sha(output / 'patched.C')
source.write_bytes(patched)
compiled = rebuild([patch.SOURCE], output / 'compiled')
assert set(compiled['artifacts']) == {'libspell_executor313.so'}
recipes = {}
for relative in ('source_port/prompt_startup_patches.py', 'conformance/prompt_startup_build.py',
                 'conformance/prompt_startup_probe.py', 'distribution/incremental_native.py'):
    target = output / Path(relative).name
    shutil.copyfile(ROOT / relative, target)
    recipes[target.name] = sha(target)
report = dict(passed=True, source=patch.SOURCE, original_sha256=sha(output / 'original.C'),
    preimage_sha256=sha(output / 'ported.C'), patched_sha256=sha(output / 'patched.C'),
    probes=probes, probes_sha256=sha(output / 'probes/result.json'), recipes=recipes,
    artifacts={name: row['sha256'] for name, row in compiled['artifacts'].items()},
    original_artifacts={name: row['original_sha256'] for name, row in compiled['artifacts'].items()},
    incremental_build_sha256=sha(output / 'compiled/incremental-build.json'),
    full_release_accepted=False)
(output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
