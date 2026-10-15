"""Capture the installed runtime and an optional explicitly declared native overlay."""
import hashlib
import json
from pathlib import Path

from installed_provenance import capture as installed_capture

SITE = Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE = Path('/opt/legacy-compare-patch')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def files():
    return {p.relative_to(SITE).as_posix(): sha(p)
            for package in ('spell', 'spell_native', 'openbexi_dss_proxy', 'openbexi_spell_dss')
            for p in (SITE / package).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def capture():
    baseline = EVIDENCE / 'baseline.json'
    if not baseline.exists():
        return dict(integrated=installed_capture(), installed=files(), overlay=None)
    base = json.loads(baseline.read_bytes())
    manifest = json.loads((EVIDENCE / 'manifest.json').read_bytes())
    expected = dict(base['installed'])
    for name, digest in manifest['artifacts'].items():
        path = 'spell_native/bin/' + name
        assert expected[path] == manifest['original_artifacts'][name]
        assert sha(EVIDENCE / 'compiled' / name) == digest
        expected[path] = digest
    actual = files()
    assert actual == expected, 'Undeclared installed payload change'
    for name, row in manifest['sources'].items():
        for label in ('original', 'ported', 'patched'):
            assert sha(EVIDENCE / label / name) == row[label + '_sha256']
    for name, digest in manifest['recipes'].items():
        assert sha(EVIDENCE / name) == digest
    return dict(integrated=base['integrated'], installed=actual, overlay=manifest,
                baseline_sha256=sha(baseline), profile='fresh-wheel-plus-declared-native-overlay/1')
