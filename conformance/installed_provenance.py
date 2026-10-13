"""Verify and capture fresh-wheel provenance without inventing overlay paths.

This verifies installed artifacts and recorded source composition. Behavioral
qualification still comes from each independent native/IPC conformance runner.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

PROFILE = 'original-spell-integrated-wheel/1'


def digest(content):
    return hashlib.sha256(content).hexdigest()


def below(root, name):
    target = (root/name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Provenance path leaves its package root: '+name)
    return target


def capture():
    spec = importlib.util.find_spec('spell_native')
    if spec is None or spec.origin is None:
        return None
    root = Path(spec.origin).parent
    manifest_path = root/'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    composition = manifest.get('composition')
    if composition is None:
        return None  # An explicitly different, historical diagnostic profile.
    if set(composition) != {'native','python'}:
        raise ValueError('Incomplete native/Python wheel composition')
    archive = root/'provenance/SPELL2.6.10-src.zip'
    if digest(archive.read_bytes()) != manifest['archive_sha256']:
        raise ValueError('Installed original archive differs')
    if digest((root/'provenance/NATIVE_GATE_POLICY.json').read_bytes()) != manifest['native_gate_policy_sha256']:
        raise ValueError('Installed native gate policy differs')
    actual = {}
    for name, expected in manifest['native_artifacts'].items():
        actual[name] = digest(below(root/'bin',name).read_bytes())
        if actual[name] != expected:
            raise ValueError('Installed native artifact differs: '+name)
    python = {}
    for name, expected in manifest['python_sources'].items():
        python[name] = digest(below(root.parent,name).read_bytes())
        if python[name] != expected:
            raise ValueError('Installed Python source differs: '+name)
    if composition['native']['recipes'] != composition['python']['recipes']:
        raise ValueError('Native and Python composition recipes differ')
    for kind, record in composition.items():
        evidence = root/('provenance/integrated-'+kind)
        encoded = (evidence/'manifest.json').read_bytes()
        if digest(encoded) != record['manifest_sha256'] or json.loads(encoded) != {
                key:value for key,value in record.items() if key != 'manifest_sha256'}:
            raise ValueError('Installed composition manifest differs: '+kind)
        if record['schema'] != 'openbexi.spell.integrated-'+kind+'/1' or record['archive_sha256'] != manifest['archive_sha256']:
            raise ValueError('Unexpected installed composition profile: '+kind)
        for name, row in record['sources'].items():
            for label, expected in row.items():
                if label not in ('original_sha256','ported_sha256','patched_sha256'):
                    raise ValueError('Unexpected composition source identity: '+label)
                if digest(below(evidence/label.removesuffix('_sha256'),name).read_bytes()) != expected:
                    raise ValueError('Installed composition source differs: '+name)
            if kind == 'python' and python.get(name) != row['patched_sha256']:
                raise ValueError('Installed Python differs from its checked correction: '+name)
        for name, row in record['recipes'].items():
            contents = below(evidence/'recipes',name).read_bytes()
            if digest(contents) != row['sha256'] or digest(contents.replace(b'\r\n',b'\n')) != row['lf_sha256']:
                raise ValueError('Installed composition recipe differs: '+name)
            if contents != below(root/'provenance/source_port',name).read_bytes():
                raise ValueError('Installed source recipe copies differ: '+name)
        if kind == 'python' and 'stages' in record:
            state = {name: row['ported_sha256'] for name,row in record['sources'].items()}
            for stage in record['stages']:
                if stage['recipe'] not in record['recipes']:
                    raise ValueError('Unknown Python composition stage')
                for name, row in stage['sources'].items():
                    if state.get(name) != row['before_sha256']:
                        raise ValueError('Broken Python composition chain: '+name)
                    state[name] = row['after_sha256']
            if state != {name: row['patched_sha256'] for name,row in record['sources'].items()}:
                raise ValueError('Python composition chain output differs')
    identity = composition['native']['checkpoint']['integrated_identity']
    if identity.encode() not in (root/'bin/libspell_executor313.so').read_bytes():
        raise ValueError('Installed native runtime lacks the composed checkpoint identity')
    driver = None
    if importlib.util.find_spec('openbexi_dss_proxy') is not None and importlib.util.find_spec('openbexi_dss_proxy.provenance') is not None:
        from openbexi_dss_proxy.provenance import capture as capture_driver
        driver = capture_driver(composition['native']['recipes'])
    return {'profile':PROFILE,'manifest_sha256':digest(manifest_path.read_bytes()),
            'manifest':manifest,'native_artifacts':actual,'python_sources':python,
            'driver_composition':driver}


def input_paths(root):
    """Bind all current checked recipes before launching the independent client."""
    return ['conformance/installed_provenance.py', 'source_port/flow_analyze.py',
            *[path.relative_to(root).as_posix() for path in sorted((root/'source_port').glob('*patches.py'))],
            'driver_plugin/pyproject.toml',
            *[path.relative_to(root).as_posix() for path in sorted((root/'driver_plugin/src').rglob('*.py'))
              if '__pycache__' not in path.parts]]


def verify_capture(record, inputs, normalized=None):
    if record is None:
        return
    if record['profile'] != PROFILE:
        raise ValueError('Unexpected installed runtime provenance profile')
    normalized = normalized or {}
    for name, row in record['manifest']['composition']['native']['recipes'].items():
        source = 'source_port/'+name
        if row['sha256'] != inputs.get(source) and row['lf_sha256'] != normalized.get(source):
            raise ValueError('Installed composition recipe differs from qualification input: '+name)
    driver = record.get('driver_composition')
    if driver is not None:
        manifest = driver['manifest']
        if driver['profile'] != 'repository-dss-integrated-wheel/1' or manifest['recipes'] != record['manifest']['composition']['native']['recipes']:
            raise ValueError('Unexpected composed driver provenance profile or recipes')
        for name, value in manifest['python_sources'].items():
            expected = manifest['sources'].get(name, {}).get('original_sha256', value)
            if expected not in (inputs.get('driver_plugin/src/'+name), normalized.get('driver_plugin/src/'+name)):
                raise ValueError('Installed driver differs from qualification source input: '+name)


def capture_client(client, inputs, normalized=None):
    """Read the exact image used by an already launched native DAP client."""
    encoded = subprocess.check_output(['docker','exec',client.name,'python','-I',
                                      '/workspace/installed_provenance.py'],timeout=30)
    record = json.loads(encoded)
    verify_capture(record, inputs, normalized)
    return record


if __name__ == '__main__':
    print(json.dumps(capture(),sort_keys=True))
