"""Audit the original installation before the explicit native diagnostic overlay."""
import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).parent))
from installed_provenance import capture

root = Path('/opt/child-lifecycle-patch')
baseline = capture()
(root/'baseline-installed.json').write_text(json.dumps(baseline, indent=2)+'\n')
(root/'baseline-bridge.json').write_text(json.dumps({
    name: hashlib.sha256((Path('/bridge')/name).read_bytes()).hexdigest()
    for name in ('spell-host-ipc', 'build.json')}, indent=2)+'\n')
manifest = json.loads((root/'manifest.json').read_bytes())
package = Path(importlib.util.find_spec('spell_native').origin).parent
for name, original in manifest['original_artifacts'].items():
    assert baseline['native_artifacts'][name] == original
    shutil.copyfile(root/'compiled'/name, package/'bin'/name)
