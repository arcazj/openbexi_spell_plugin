"""Retain verified wheel identity before installing the diagnostic library."""
import importlib.util
import json
from pathlib import Path
import shutil

from installed_provenance import capture

root = Path('/opt/ipc-mailbox-patch')
baseline = capture()
assert baseline is not None
(root / 'baseline-installed.json').write_text(json.dumps(baseline, indent=2) + '\n')
manifest = json.loads((root / 'manifest.json').read_bytes())
package = Path(importlib.util.find_spec('spell_native').origin).parent
assert set(manifest['artifacts']) == {'libspell_executor313.so', 'SPELL-Context', 'SPELL-Listener'}
assert set(manifest['original_artifacts']) == set(manifest['artifacts'])
for name, original in manifest['original_artifacts'].items():
    assert baseline['native_artifacts'][name] == original
    shutil.copyfile(root / 'compiled' / name, package / 'bin' / name)
