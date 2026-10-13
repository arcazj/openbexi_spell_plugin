"""Reject stale or tampered wheel inputs before building runtime images."""
import base64
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

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
