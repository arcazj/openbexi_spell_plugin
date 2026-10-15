"""Declare a single diagnostic value-import overlay over the verified wheel."""
import hashlib
import json
from pathlib import Path
import sys

from installed_provenance import capture as installed_capture

SITE = Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE = Path('/opt/database-values-patch')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def installed_files():
    return {path.relative_to(SITE).as_posix(): sha(path)
            for package in ('spell', 'spell_native', 'openbexi_dss_proxy', 'openbexi_spell_dss')
            for path in (SITE / package).rglob('*')
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'}


def capture():
    path = EVIDENCE / 'base.json'
    if not path.exists():
        return dict(integrated=installed_capture(), installed=installed_files(), overlay=None)
    base = json.loads(path.read_bytes())
    expected = dict(base['installed'])
    manifest = json.loads((EVIDENCE / 'manifest.json').read_bytes())
    assert set(manifest) == {'spell/utils/vimport.py'}
    for name, row in manifest.items():
        assert expected[name] == row['preimage_sha256'] == sha(EVIDENCE / 'original' / name)
        assert row['sha256'] == sha(EVIDENCE / 'patched' / name)
        expected[name] = row['sha256']
    actual = installed_files()
    if actual != expected:
        raise ValueError('Undeclared overlay changes: ' + repr(sorted(
            name for name in set(actual) | set(expected) if actual.get(name) != expected.get(name))))
    files = {p.relative_to(EVIDENCE).as_posix(): sha(p) for p in EVIDENCE.rglob('*')
             if p.is_file() and p.name != 'base.json' and '__pycache__' not in p.parts}
    return dict(integrated=base['integrated'], installed=actual,
        overlay={'manifest': manifest, 'files': files}, base_sha256=sha(path),
        profile='fresh-wheel-plus-declared-diagnostic-overlay/1')


if __name__ == '__main__':
    if sys.argv[1:] == ['--freeze-base']:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        path = EVIDENCE / 'base.json'
        if path.exists():
            raise ValueError('Refusing to replace frozen base evidence')
        path.write_text(json.dumps(capture(), indent=2) + '\n', encoding='utf-8')
    else:
        print(json.dumps(capture(), indent=2))
