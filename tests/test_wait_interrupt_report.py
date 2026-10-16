"""Reject self-consistent but contradicted native wait-control evidence."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from wait_interrupt_report import qualify as _qualify

def qualify(*args):
    return _qualify(*args, source_revision='86f4de71a1f7ed12610c60462c72fae44387b353', baseline_revision='07973612ef970473492b22a98be8c7058c2f1263')


@pytest.fixture(scope='module')
def proof():
    report=json.loads((ROOT/'conformance/evidence/wait_interrupt.json').read_bytes())
    return Path(report['raw']['path']),Path(report['baseline']['path']),report['runtime_image']


def test_all_native_wait_controls_are_required(proof):
    report=qualify(*proof)
    assert report['qualified_contracts']==[] and len(report['candidate_contracts'])==8 and len(report['checks'])==28
    assert not report['full_v05_accepted']


@pytest.mark.parametrize('change',['missing','state','deadline','reacquisition','wrong-tm','wrong-command'])
def test_contradicted_wait_observations_cannot_qualify(proof,tmp_path,change):
    original,baseline,image=proof
    raw=json.loads(original.read_bytes())
    shutil.copytree(original.parent/'workspace',tmp_path/'workspace')
    if change=='missing':del raw['checks']['telemetry:skip:recovery']
    elif change=='state':
        row=raw['checks']['relative:step:positive']
        row['states']=[x for x in row['states'] if x['status']!='INTERRUPTED']
    elif change=='deadline':
        row=raw['checks']['absolute:step:boundary'];row['paused_at']=row['actions'][-2]['epoch']+5
    elif change=='reacquisition':
        row=raw['checks']['telemetry:skip:boundary']
        row['rpc'].append(dict(path='/RefreshItem',started=(row['held']['since']+row['held']['until'])/2))
    elif change=='wrong-tm':raw['checks']['telemetry:step:positive']['last_tm_value']=-1
    else:raw['checks']['relative:skip:positive']['actions'][-2]['command']='CMD_RUN'
    (tmp_path/'workspace/checks.json').write_text(json.dumps(raw['checks']))
    path=tmp_path/'result.json';path.write_text(json.dumps(raw))
    with pytest.raises((AssertionError,ValueError)):qualify(path,baseline,image)
