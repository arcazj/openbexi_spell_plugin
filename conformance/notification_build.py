"""Apply only the checked Notify compatibility recipe over an audited wheel."""
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, '/opt/notification-input')
from installed_provenance import capture
from notification_patches import apply_tree

root = Path(importlib.util.find_spec('spell_native').origin).parent
baseline = capture()
assert baseline is not None
output = Path('/opt/notification-patch')
apply_tree(root.parent, root/'provenance/SPELL2.6.10-src.zip', output)
(output/'baseline-installed.json').write_text(json.dumps(baseline, indent=2)+'\n')
