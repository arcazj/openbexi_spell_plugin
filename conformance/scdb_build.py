"""Build typed-database baseline and optional named-SCDB read-only candidate."""
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,'/opt/scdb-input')
from installed_provenance import capture
from database_import_patches import apply_tree as import_tree
from scdb_patches import apply_tree

root = Path(importlib.util.find_spec('spell_native').origin).parent
baseline = capture()
assert baseline is not None
Path('/opt/scdb-input/baseline-installed.json').write_text(json.dumps(baseline,indent=2)+'\n')
import_tree(root.parent, Path('/opt/database-import-patch'))
if os.environ['APPLY_SCDB'] == '1':
    apply_tree(root.parent, root/'provenance/SPELL2.6.10-src.zip', Path('/opt/scdb-patch'))
