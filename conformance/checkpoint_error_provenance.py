"""Verify original installation plus the one explicitly retained native overlay."""
import hashlib
import importlib.util
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    overlay=Path('/opt/checkpoint-error-patch')
    base=json.loads((overlay/'baseline-installed.json').read_bytes())
    report=json.loads((overlay/'manifest.json').read_bytes())
    root=Path(importlib.util.find_spec('spell_native').origin).parent
    assert sha(root/'manifest.json')==base['manifest_sha256']
    for name,expected in base['python_sources'].items():
        assert sha(root.parent/name)==expected,name
    for name,expected in base['native_artifacts'].items():
        assert sha(root/'bin'/name)==report['artifacts'].get(name,expected),name
    for label in ('original','ported','patched'):
        assert sha(overlay/label/report['source'])==report['sources'][label+'_sha256']
    for name,expected in report['recipes'].items():
        assert sha(overlay/name)==expected,name
    return dict(baseline=base,checkpoint_overlay=report)
