"""Run existing real binary driver regressions using the checked Ground source.

Only the Ground class is loaded from recipe output in this test process. The
dispatcher, gRPC server, transport, journal, actual DSS engine and packet paths
are the existing implementations. No repository or installed source is rewritten.
"""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'driver_plugin/src'))
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'source_port'))
import rng_state_patches
import openbexi_spell_dss.ground as ground
import pytest


def main():
    output=ROOT/'.qualification/rng-state-driver'/uuid.uuid4().hex
    output.mkdir(parents=True)
    source_name='openbexi_spell_dss/ground.py'
    before=(ROOT/'driver_plugin/src'/source_name).read_bytes()
    patched=rng_state_patches.apply(source_name,before)
    inputs=['source_port/rng_state_patches.py','tests/test_rng_state_patch.py',
            'tests/test_original_driver.py','conformance/check_rng_state_driver.py']
    inputs += [p.relative_to(ROOT).as_posix() for p in (ROOT/'driver_plugin/src').rglob('*.py') if '__pycache__' not in p.parts]
    inputs += [p.relative_to(ROOT).as_posix() for p in (ROOT/'src/dss').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in inputs}
    helper=runpy.run_path(str(ROOT/'tests/test_rng_state_patch.py'))
    original=ground.Ground
    ground.Ground=helper['candidate']()
    try:
        result=pytest.main(['-q',str(ROOT/'tests/test_original_driver.py'),
            '--basetemp',str(output/'workspace'),'--junitxml',str(output/'junit.xml')])
    finally:
        ground.Ground=original
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected for name,expected in hashes.items())
    report=dict(passed=result==0,exit_code=int(result),
        inputs=hashes,
        ground_preimage=hashlib.sha256(before).hexdigest(),ground_patched=hashlib.sha256(patched).hexdigest(),
        scope='Existing real binary driver regression suite with checked Ground class; no native SPELL qualification claim.')
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),passed=report['passed'])))
    return int(result)


if __name__=='__main__':raise SystemExit(main())
