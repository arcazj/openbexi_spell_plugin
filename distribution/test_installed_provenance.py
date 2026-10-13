"""Qualification input binding for installed composition provenance."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'conformance'))
from installed_provenance import PROFILE, below, verify_capture, verify_stages


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


@pytest.mark.parametrize('mutation',['none','missing','reversed','wrong-before','wrong-after','unknown-recipe','unknown-source'])
def test_native_recovery_stages_preserve_checked_data_preimage(mutation):
    data=dict(recipes={'data_files_native_patches.py':{},'checkpoint_context_patches.py':{}},
        sources={'context.C':dict(ported_sha256='central',patched_sha256='recovery')},stages=[
            dict(recipe='data_files_native_patches.py',sources={'context.C':dict(before_sha256='central',after_sha256='data')}),
            dict(recipe='checkpoint_context_patches.py',sources={'context.C':dict(before_sha256='data',after_sha256='recovery')})])
    if mutation=='missing':data.pop('stages')
    elif mutation=='reversed':data['stages'].reverse()
    elif mutation=='wrong-before':data['stages'][1]['sources']['context.C']['before_sha256']='central'
    elif mutation=='wrong-after':data['stages'][1]['sources']['context.C']['after_sha256']='unqualified'
    elif mutation=='unknown-recipe':data['stages'][1]['recipe']='other.py'
    elif mutation=='unknown-source':data['stages'][1]['sources']['other.C']=data['stages'][1]['sources'].pop('context.C')
    if mutation=='none':verify_stages('native',data)
    else:
        with pytest.raises(ValueError):verify_stages('native',data)
