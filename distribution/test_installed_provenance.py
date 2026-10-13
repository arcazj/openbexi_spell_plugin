"""Qualification input binding for installed composition provenance."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'conformance'))
from installed_provenance import PROFILE, below, verify_capture


def record():
    return {'profile':PROFILE,'manifest':{'composition':{'native':{'recipes':{
        'qualified_patches.py':{'sha256':'raw','lf_sha256':'normalized'}}}}}}


def test_qualification_requires_exact_recipe_or_normalized_input():
    verify_capture(record(), {'source_port/qualified_patches.py':'raw'})
    verify_capture(record(), {'source_port/qualified_patches.py':'crlf'},
                   {'source_port/qualified_patches.py':'normalized'})
    with pytest.raises(ValueError,match='differs from qualification input'):
        verify_capture(record(), {'source_port/qualified_patches.py':'other'})
    with pytest.raises(ValueError,match='differs from qualification input'):
        verify_capture(record(), {})


def test_unknown_profile_is_not_treated_as_qualified_wheel():
    changed = record()
    changed['profile'] = 'unqualified'
    with pytest.raises(ValueError,match='Unexpected installed runtime'):
        verify_capture(changed,{})


def test_provenance_path_must_stay_inside_package(tmp_path):
    root = tmp_path/'package'
    assert below(root,'native/file') == root/'native/file'
    with pytest.raises(ValueError,match='leaves its package root'):
        below(root,'../package-other/file')


def test_qualification_binds_driver_repository_preimage_and_support_inputs():
    data = record()
    recipes = data['manifest']['composition']['native']['recipes']
    data['driver_composition'] = {'profile':'repository-dss-integrated-wheel/1', 'manifest':{
        'recipes':recipes, 'python_sources':{'proxy/tm.py':'patched','proxy/support.py':'support'},
        'sources':{'proxy/tm.py':{'original_sha256':'repository','patched_sha256':'patched'}}}}
    inputs = {'source_port/qualified_patches.py':'raw',
              'driver_plugin/src/proxy/tm.py':'repository','driver_plugin/src/proxy/support.py':'support'}
    verify_capture(data, inputs)
    inputs['driver_plugin/src/proxy/tm.py'] = 'patched'
    with pytest.raises(ValueError, match='qualification source input'):
        verify_capture(data, inputs)
