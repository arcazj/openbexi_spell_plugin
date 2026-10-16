"""Preserve installed-wheel provenance before replacing the diagnostic library."""
import importlib.util
import json
from pathlib import Path
import shutil

from installed_provenance import capture

overlay = Path('/opt/prompt-startup-patch')
base = capture()
assert base is not None
(overlay / 'baseline-installed.json').write_text(json.dumps(base, indent=2) + '\n')
record = json.loads((overlay / 'manifest.json').read_bytes())
assert set(record['artifacts']) == set(record['original_artifacts']) == {'libspell_executor313.so'}
root = Path(importlib.util.find_spec('spell_native').origin).parent
for name, expected in record['original_artifacts'].items():
    assert base['native_artifacts'][name] == expected
    shutil.copyfile(overlay / 'compiled' / name, root / 'bin' / name)
