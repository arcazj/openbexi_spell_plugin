"""Verify original installation and the retained child lifecycle native overlay."""
import hashlib
import importlib.util
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    overlay = Path('/opt/child-lifecycle-patch')
    base = json.loads((overlay/'baseline-installed.json').read_bytes())
    report = json.loads((overlay/'manifest.json').read_bytes())
    root = Path(importlib.util.find_spec('spell_native').origin).parent
    assert sha(root/'manifest.json') == base['manifest_sha256']
    for name, expected in base['python_sources'].items():
        assert sha(root.parent/name) == expected, name
    for name, expected in base['native_artifacts'].items():
        assert sha(root/'bin'/name) == report['artifacts'].get(name, expected), name
    for name, hashes in report['sources'].items():
        for label in ('original', 'ported', 'patched'):
            assert sha(overlay/label/name) == hashes[label+'_sha256']
    for name, expected in report['recipes'].items():
        assert sha(overlay/name) == expected, name
    bridge = json.loads((overlay/'baseline-bridge.json').read_bytes())
    for name, expected in bridge.items():
        assert sha(Path('/bridge')/name) == expected, name
    return dict(baseline=base, child_lifecycle_overlay=report,
                unchanged_bridge=bridge)
