"""Reject incomplete controls or altered binaries for the prompt transition fix."""
import copy
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from prompt_startup_report import qualify, verify_export, verify_run


@pytest.fixture(scope='module')
def evidence():
    record=json.loads((ROOT/'conformance/evidence/prompt_startup.json').read_bytes())
    paths={name:Path(row['path']) for name,row in record['raw'].items()}
    runtime=json.loads(paths['early'].read_bytes())['runtime_sources']
    return record, paths, Path(record['export']['path']), runtime


def test_prompt_transition_evidence_preserves_all_controls(evidence):
    record, paths, directory, runtime=evidence
    actual=qualify(Path(record['candidate']['path']),directory,Path(record['retained_failure']['path']),
        Path(record['debugger']['result']['path']).parent,source_revision='a4011ed')
    assert sum(actual['passed_checks'].values())==109
    assert not actual['full_v05_accepted'] and actual['qualified_contracts']==[]


@pytest.mark.parametrize('name',['patched.C','prompt_startup_patches.py','compiled/libspell_executor313.so',
    'compiled/incremental-build.json','probes/original-probe.cpp','probes/patched-run.log'])
def test_altered_prompt_export_is_rejected(evidence,tmp_path,name):
    _,_,original,runtime=evidence
    directory=tmp_path/'export'
    shutil.copytree(original,directory)
    path=directory/name
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises((AssertionError,ValueError)):
        verify_export(directory,runtime)


@pytest.mark.parametrize('alteration',['missing','failed','wrong-source','wrong-archive'])
def test_incomplete_or_changed_native_controls_are_rejected(evidence,alteration):
    _,paths,_,_=evidence
    path=paths['early']
    raw=copy.deepcopy(json.loads(path.read_bytes()))
    if alteration=='missing': raw['checks'].pop('close-none-0')
    elif alteration=='failed': raw['checks']['close-none-0']['passed']=False
    elif alteration=='wrong-source': raw['generated_sources']['child_lifecycle_controller.py']='0'*64
    else: raw['workspace_sha256']='0'*64
    with pytest.raises(AssertionError): verify_run(path,raw,'early')
