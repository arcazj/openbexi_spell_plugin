"""Verify an exact fresh-wheel base and every display-only Python change."""
import hashlib
import json
from pathlib import Path
import sys
from installed_provenance import capture as installed_capture

SITE = Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE = Path('/opt/display-patch')
ADDED = ('openbexi_spell_dss/displays.py', 'openbexi_spell_dss/display_viewer.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {path.relative_to(SITE).as_posix(): digest(path)
            for package in ('spell', 'spell_native', 'openbexi_dss_proxy', 'openbexi_spell_dss')
            for path in (SITE / package).rglob('*')
            if path.is_file() and (path.suffix in ('.py', '.so') or path.parent.name == 'bin')}


def capture():
    base_path = EVIDENCE / 'base.json'
    if not base_path.exists():
        return dict(integrated=installed_capture(), installed=sources(), overlay=None)
    base = json.loads(base_path.read_bytes())
    expected = dict(base['installed'])
    manifest = json.loads((EVIDENCE / 'manifest.json').read_bytes())
    for name, row in manifest.items():
        if expected.get(name) != row['preimage_sha256']:
            raise ValueError('Display preimage differs from frozen installed source: ' + name)
        if (digest(EVIDENCE / 'original' / name) != row['preimage_sha256']
                or digest(EVIDENCE / 'patched' / name) != row['sha256']):
            raise ValueError('Display source evidence changed: ' + name)
        expected[name] = row['sha256']
    additions = {}
    for name in ADDED:
        if name in expected:
            raise ValueError('Display addition overwrites a base source: ' + name)
        additions[name] = expected[name] = digest(EVIDENCE / 'modules' / name)
    actual = sources()
    if actual != expected:
        raise ValueError('Undeclared display source changes: ' + repr(sorted(
            name for name in set(actual) | set(expected) if actual.get(name) != expected.get(name))))
    integrated = base['integrated']
    if digest(SITE / 'spell_native/manifest.json') != integrated['manifest_sha256']:
        raise ValueError('Base native wheel manifest changed')
    for kind, record in integrated['manifest']['composition'].items():
        directory = SITE / 'spell_native/provenance' / ('integrated-' + kind)
        if digest(directory / 'manifest.json') != record['manifest_sha256']:
            raise ValueError('Base composition manifest changed')
        for name, row in record['recipes'].items():
            if digest(directory / 'recipes' / name) != row['sha256']:
                raise ValueError('Base composition recipe changed')
    return dict(integrated=integrated, installed=actual, base_sha256=digest(base_path),
        profile='fresh-wheel-plus-declared-display-overlay/1', overlay=dict(manifest=manifest,
            added_sources=additions, files={path.relative_to(EVIDENCE).as_posix(): digest(path)
                for path in EVIDENCE.rglob('*') if path.is_file() and path.name != 'base.json'}))


if __name__ == '__main__':
    if sys.argv[1:] == ['--freeze-base']:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        target = EVIDENCE / 'base.json'
        if target.exists():
            raise ValueError('Refusing to replace frozen display base')
        target.write_text(json.dumps(capture(), indent=2) + '\n')
    else:
        print(json.dumps(capture(), indent=2))
