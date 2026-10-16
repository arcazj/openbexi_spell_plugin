"""Retained native ranging bytes include the later display composition stage."""
import copy
import hashlib
import subprocess
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from rng_composed_review import verify_composed


@pytest.fixture(scope='module')
def captured():
    # Immutable command candidate: the observer and runtime remain unchanged.
    proof=json.loads(subprocess.check_output(['git','show','ffc6d660a111e9478f8a1d0280651f37d2dfb10d:conformance/evidence/rng.json'],cwd=ROOT))
    path=Path(proof['raw_report_path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==proof['raw_report_sha256']
    raw=json.loads(path.read_bytes())
    return raw


def test_actual_display_composition_is_checked_to_its_installed_bytes(captured):
    row=verify_composed(captured['runtime_sources'],captured['inputs'],captured['lf_normalized_inputs'])
    assert row['patched_sha256']=='e2a72ed8b333499892c9cf456317ac1dec23da641af7999a0358600ce9811461'


@pytest.mark.parametrize('mutation',[
    'missing-state','missing-display','unbound-recipe','broken-chain',
    'wrong-installed','wrong-final','undeclared-terminal',
])
def test_missing_or_forged_source_chain_is_rejected(captured,mutation):
    raw=copy.deepcopy(captured);runtime=raw['runtime_sources']
    driver=runtime['integrated']['driver_composition']['manifest']
    name='openbexi_spell_dss/ground.py'
    if mutation=='missing-state':
        driver['stages']=[s for s in driver['stages'] if s['recipe']!='rng_state_patches.py']
    elif mutation=='missing-display':
        driver['stages']=[s for s in driver['stages'] if s['recipe']!='display_patches.py']
    elif mutation=='unbound-recipe':driver['recipes']['display_patches.py']['sha256']='0'*64
    elif mutation=='wrong-installed':runtime['installed'][name]='0'*64
    elif mutation=='wrong-final':driver['sources'][name]['patched_sha256']='0'*64
    else:
        stage=next(s for s in driver['stages'] if s['recipe']=='display_patches.py')
        if mutation=='broken-chain':stage['sources'][name]['before_sha256']='0'*64
        else:stage['recipe']='rng_state_patches.py'
    with pytest.raises((AssertionError,ValueError)):
        verify_composed(runtime,raw['inputs'],raw['lf_normalized_inputs'])
