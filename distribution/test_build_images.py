"""Reject stale or tampered wheel inputs before building runtime images."""
import base64
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile
import shutil

import pytest

spec = importlib.util.spec_from_file_location('build_images', Path(__file__).with_name('build_images.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def wheel(path, recipes=None, tamper=False):
    binary, python = b'preserved-native-payload', b'print(42)\n'
    manifest = {'native_artifacts':{'runtime':hashlib.sha256(binary).hexdigest()},
                'python_sources':{'spell/test.py':hashlib.sha256(python).hexdigest()}, 'composition':{
        kind:{'recipes':recipes if recipes is not None else builder.recipe_hashes()}
        for kind in ('native','python')}}
    entries = {'spell_native/manifest.json':json.dumps(manifest).encode(),
               'spell_native/bin/runtime':binary, 'spell/test.py':python}
    record = 'package-1.dist-info/RECORD'
    stream = io.StringIO(newline='')
    writer = csv.writer(stream,lineterminator='\n')
    for name, contents in entries.items():
        encoded = base64.urlsafe_b64encode(hashlib.sha256(contents).digest()).rstrip(b'=').decode()
        writer.writerow((name,'sha256='+encoded,len(contents)))
    writer.writerow((record,'',''))
    entries[record] = stream.getvalue().encode()
    if tamper:
        entries['spell/test.py'] = b'unqualified edit\n'
    with zipfile.ZipFile(path,'w') as archive:
        for name, contents in entries.items():
            archive.writestr(name,contents)


def test_selected_wheel_binds_current_composition_and_complete_record(tmp_path):
    path = tmp_path/'selected.whl'
    wheel(path)
    result = builder.inspect_wheel(path,require_composition=True)
    assert result['sha256'] == builder.sha(path)
    assert result['record_files_verified'] == 3
    assert result['composition']['native']['recipes'] == builder.recipe_hashes()


def test_tampered_payload_is_rejected_before_image_build(tmp_path):
    path = tmp_path/'tampered.whl'
    wheel(path,tamper=True)
    with pytest.raises(ValueError,match='Wheel RECORD mismatch: spell/test.py'):
        builder.inspect_wheel(path,require_composition=True)


def test_valid_record_does_not_allow_stale_recipe_composition(tmp_path):
    path = tmp_path/'stale.whl'
    recipes = builder.recipe_hashes()
    recipes['dta_time_patches.py']['lf_sha256'] = '0'*64
    wheel(path,recipes=recipes)
    with pytest.raises(ValueError,match='predates the current composed recipes'):
        builder.inspect_wheel(path,require_composition=True)


@pytest.mark.parametrize('change', ['unchanged','extra-python','changed-payload'])
def test_fully_rehashed_driver_wheel_still_requires_composition_source_set(tmp_path, change):
    source = tmp_path/'src'
    shutil.copytree(builder.ROOT/'driver_plugin/src',source,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    builder.apply_driver_tree(source,source/'openbexi_dss_proxy/_composition')
    entries={path.relative_to(source).as_posix():path.read_bytes() for path in source.rglob('*') if path.is_file()}
    if change=='extra-python':
        entries['openbexi_dss_proxy/unrecorded.py']=b'answer=42\n'
    elif change=='changed-payload':
        entries['openbexi_dss_proxy/tm.py']+=b'\n# correctly rehashed but not qualified\n'
    record='driver-1.dist-info/RECORD'
    stream=io.StringIO(newline='')
    writer=csv.writer(stream,lineterminator='\n')
    for name,contents in sorted(entries.items()):
        encoded=base64.urlsafe_b64encode(hashlib.sha256(contents).digest()).rstrip(b'=').decode()
        writer.writerow((name,'sha256='+encoded,len(contents)))
    writer.writerow((record,'',''))
    entries[record]=stream.getvalue().encode()
    path=tmp_path/'driver.whl'
    with zipfile.ZipFile(path,'w') as archive:
        for name,contents in entries.items():
            archive.writestr(name,contents)
    if change=='unchanged':
        assert builder.inspect_wheel(path,require_driver_composition=True)['driver_composition']
    else:
        expected='complete wheel Python source set' if change=='extra-python' else 'Driver Python source differs'
        with pytest.raises(ValueError,match=expected):
            builder.inspect_wheel(path,require_driver_composition=True)
