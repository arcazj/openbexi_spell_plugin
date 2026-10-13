"""Audit the full parent installation and each selected diagnostic overlay byte."""
import hashlib
import importlib.util
import json
from pathlib import Path
from installed_provenance import capture


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def capture_notification():
    evidence = Path('/opt/notification-patch')
    if not evidence.exists():
        return dict(baseline=capture(), overlay=None)
    baseline = json.loads((evidence/'baseline-installed.json').read_bytes())
    encoded = (evidence/'manifest.json').read_bytes()
    overlay = json.loads(encoded)
    root = Path(importlib.util.find_spec('spell_native').origin).parent
    assert digest((root/'manifest.json').read_bytes()) == baseline['manifest_sha256']
    assert digest((evidence/'notification_patches.py').read_bytes()) == overlay['recipe_sha256']
    for name, row in overlay['sources'].items():
        assert baseline['python_sources'][name] == row['ported_sha256']
        for label in ('original', 'ported', 'patched'):
            assert digest((evidence/label/name).read_bytes()) == row[label + '_sha256']
    for name, original in baseline['python_sources'].items():
        expected = overlay['sources'].get(name, {}).get('patched_sha256', original)
        assert digest((root.parent/name).read_bytes()) == expected, name
    for name, expected in baseline['native_artifacts'].items():
        assert digest((root/'bin'/name).read_bytes()) == expected, name
    return dict(baseline=baseline, overlay=overlay, overlay_manifest_sha256=digest(encoded))
