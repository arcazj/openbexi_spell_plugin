"""Bind a composed native run to complete wheel bytes, manifests and RECORDs."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

from installed_provenance import verify_capture
from openbexi_dss_proxy.provenance import verify as verify_driver


def sha(raw):return hashlib.sha256(raw).hexdigest()


def wheel_sources(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts for name in names)
        record, = [name for name in names if name.endswith('.dist-info/RECORD')]
        rows = list(csv.reader(io.StringIO(archive.read(record).decode('utf-8'))))
        assert len(rows) == len(names) and {row[0] for row in rows} == set(names)
        contents = {name:archive.read(name) for name in names}
        for name,digest,size in rows:
            if name == record:
                assert digest == size == ''
            else:
                expected = base64.urlsafe_b64encode(hashlib.sha256(contents[name]).digest()).rstrip(b'=').decode()
                assert digest == 'sha256='+expected and int(size) == len(contents[name])
    return contents


def verify(raw, native_wheel, driver_wheel, *, profile='fresh-composed-limit-telemetry-wheel/1',
           required_recipes=('limit_feature_patches.py','telemetry_feature_patches.py')):
    runtime = raw['runtime_sources']
    assert runtime['profile'] == profile
    assert set(runtime) == {'profile','integrated','installed'}
    integrated = runtime['integrated']
    verify_capture(integrated,raw['inputs'])
    native = wheel_sources(native_wheel)
    driver = wheel_sources(driver_wheel)
    encoded = native['spell_native/manifest.json']
    assert sha(encoded) == integrated['manifest_sha256']
    assert json.loads(encoded) == integrated['manifest']
    recipes = integrated['manifest']['composition']['native']['recipes']
    assert set(required_recipes) <= set(recipes)
    assert integrated['manifest']['composition']['python']['recipes'] == recipes
    assert verify_driver(driver.__getitem__, recipes) == integrated['driver_composition']
    assert not set(native) & set(driver)
    contents = {**native,**driver}
    prefixes = ('spell/','spell_native/','openbexi_dss_proxy/','openbexi_spell_dss/')
    expected = {name:sha(value) for name,value in contents.items() if name.startswith(prefixes)
                and (PurePosixPath(name).suffix in ('.py','.so') or PurePosixPath(name).parent.name in ('bin','limit_files'))}
    assert runtime['installed'] == expected
    for name,digest in integrated['python_sources'].items():assert expected[name] == digest
    for name,digest in integrated['native_artifacts'].items():assert expected['spell_native/bin/'+name] == digest
    for name,digest in integrated['driver_composition']['manifest']['python_sources'].items():assert expected[name] == digest
    resource = 'openbexi_spell_dss/limit_files/normal.json'
    assert expected[resource] == raw['inputs']['driver_plugin/src/'+resource]
    return dict(passed=True,native_wheel={'path':str(native_wheel.resolve()),'sha256':sha(native_wheel.read_bytes())},
                driver_wheel={'path':str(driver_wheel.resolve()),'sha256':sha(driver_wheel.read_bytes())},
                installed_files=len(expected),complete_records_verified=True)
