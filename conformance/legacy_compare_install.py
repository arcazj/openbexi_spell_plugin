"""Verify the original installed wheel before applying the declared native overlay."""
import json
from pathlib import Path
import shutil

from installed_provenance import capture
from legacy_compare_provenance import SITE, EVIDENCE, files, sha

baseline = {'integrated': capture(), 'installed': files()}
assert baseline['integrated'] is not None
(EVIDENCE / 'baseline.json').write_text(json.dumps(baseline, indent=2) + '\n', encoding='utf-8')
manifest = json.loads((EVIDENCE / 'manifest.json').read_bytes())
for name, original in manifest['original_artifacts'].items():
    destination = SITE / 'spell_native/bin' / name
    assert baseline['integrated']['native_artifacts'][name] == original == sha(destination)
    source = EVIDENCE / 'compiled' / name
    assert sha(source) == manifest['artifacts'][name]
    shutil.copyfile(source, destination)
