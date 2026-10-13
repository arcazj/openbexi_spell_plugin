"""Verify source composition shipped inside an independently built driver wheel."""
import base64
import hashlib
from importlib import metadata
import json
from pathlib import Path, PurePosixPath

PREFIX = 'openbexi_dss_proxy/_composition/'


def digest(content):
    return hashlib.sha256(content).hexdigest()


def verify(read, expected_recipes):
    def contents(name):
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name:
            raise ValueError('Invalid driver provenance path: '+name)
        return read(name)

    encoded = contents(PREFIX+'manifest.json')
    manifest = json.loads(encoded)
    if manifest['schema'] != 'openbexi.spell.integrated-driver/1':
        raise ValueError('Unexpected driver composition profile')
    if manifest['recipes'] != expected_recipes:
        raise ValueError('Driver and native composition recipes differ')
    for name, row in manifest['recipes'].items():
        raw = contents(PREFIX+'recipes/'+name)
        if digest(raw) != row['sha256'] or digest(raw.replace(b'\r\n', b'\n')) != row['lf_sha256']:
            raise ValueError('Driver composition recipe differs: '+name)
    for name, expected in manifest['python_sources'].items():
        if digest(contents(name)) != expected:
            raise ValueError('Driver Python source differs: '+name)
    state = {}
    for name, row in manifest['sources'].items():
        if set(row) != {'original_sha256', 'patched_sha256'}:
            raise ValueError('Incomplete driver correction source: '+name)
        for label, expected in row.items():
            if digest(contents(PREFIX+label.removesuffix('_sha256')+'/'+name)) != expected:
                raise ValueError('Driver correction evidence differs: '+name)
        state[name] = row['original_sha256']
    for stage in manifest['stages']:
        if stage['recipe'] not in manifest['recipes']:
            raise ValueError('Unknown driver composition stage')
        for name, row in stage['sources'].items():
            if state.get(name) != row['before_sha256']:
                raise ValueError('Broken driver composition chain: '+name)
            state[name] = row['after_sha256']
    for name, row in manifest['sources'].items():
        if state[name] != row['patched_sha256'] or manifest['python_sources'].get(name) != row['patched_sha256']:
            raise ValueError('Driver composition output differs: '+name)
    return {'profile':'repository-dss-integrated-wheel/1',
            'manifest_sha256':digest(encoded), 'manifest':manifest}


def capture(expected_recipes):
    root = Path(__file__).resolve().parents[1]
    if not (root/PREFIX/'manifest.json').exists():
        return None  # Repository/development profile; no composed wheel claim.
    package = metadata.distribution('openbexi-spell-dss')
    checked = 0
    recorded_sources = set()
    for entry in package.files:
        name = str(entry).replace('\\', '/')
        if entry.hash is None:
            continue
        raw = package.locate_file(entry).read_bytes()
        encoded = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
        if entry.hash.mode != 'sha256' or entry.hash.value != encoded or entry.size != len(raw):
            raise ValueError('Installed driver RECORD differs: '+name)
        if name.endswith('.py') and not name.startswith(PREFIX):
            recorded_sources.add(name)
        checked += 1
    result = verify(lambda name: (root/name).read_bytes(), expected_recipes)
    if recorded_sources != set(result['manifest']['python_sources']):
        raise ValueError('Driver composition does not cover the complete wheel Python source set')
    result['record_files_verified'] = checked
    return result
