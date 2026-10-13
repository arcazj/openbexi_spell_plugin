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
