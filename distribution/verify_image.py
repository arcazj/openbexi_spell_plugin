"""Check actual installed wheel records in a newly built diagnostic runtime."""
import base64
import hashlib
from importlib import metadata
import json
from pathlib import Path


def verify():
    distributions = {}
    for name in ('openbexi-spell-source', 'openbexi-spell-dss'):
        package = metadata.distribution(name)
        checked = 0
        for entry in package.files:
            if entry.hash is None:
                continue  # pip's generated RECORD and bytecode have no hash.
            content = package.locate_file(entry).read_bytes()
            actual = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
            if entry.hash.mode != 'sha256' or entry.hash.value != actual or entry.size != len(content):
                raise ValueError('Installed RECORD mismatch: '+str(entry))
            checked += 1
        distributions[name] = {'version':package.version, 'record_files_verified':checked}
    import spell_native
    native = Path(spell_native.__file__).parent
    manifest = json.loads((native/'manifest.json').read_text())
    assert set(manifest['composition']) == {'native', 'python'}
    for name, expected in manifest['native_artifacts'].items():
        assert hashlib.sha256((native/'bin'/name).read_bytes()).hexdigest() == expected, name
    for name, expected in manifest['python_sources'].items():
        assert hashlib.sha256((native.parent/name).read_bytes()).hexdigest() == expected, name
    bridge = json.loads(Path('/bridge/build.json').read_text())
    assert bridge['native_composition'] == manifest['composition']['native']
    assert hashlib.sha256(Path('/bridge/spell-host-ipc').read_bytes()).hexdigest() == bridge['bridge_sha256']
    from openbexi_dss_proxy.provenance import capture
    driver = capture(manifest['composition']['native']['recipes'])
    if driver is None:
        raise ValueError('Fresh image lacks composed driver provenance')
    return {'passed':True, 'distributions':distributions,
            'native_artifacts':manifest['native_artifacts'],
            'driver_composition':driver,
            'composition':manifest['composition'], 'bridge_sha256':bridge['bridge_sha256']}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
