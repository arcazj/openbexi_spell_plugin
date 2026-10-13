"""Save the audited original installation before the explicit native overlay."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).parent))
from installed_provenance import capture

root=Path('/opt/checkpoint-error-patch')
baseline=capture()
(root/'baseline-installed.json').write_text(json.dumps(baseline,indent=2)+'\n')
manifest=json.loads((root/'manifest.json').read_bytes())
package=Path(importlib.util.find_spec('spell_native').origin).parent
for name,original in manifest['original_artifacts'].items():
    assert baseline['native_artifacts'][name]==original
    shutil.copyfile(root/'compiled'/name,package/'bin'/name)
