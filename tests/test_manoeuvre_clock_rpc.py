"""Read-only database clock traffic must retain its exact wire contract."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from manoeuvre_database_review import verify_read_only_rpc


def captured():
    return dict(initial_dss=dict(clock_epoch_unix_ns=0,core=dict(sim_time_ns=0)),rpc=[
        dict(path='/spell.driver.SPELLDriverInterface_EV/RaiseEvent',response=''),
        dict(path='/spell.driver.SPELLDriverInterface_TIME/GetUTC',
             request='0a25747970652e676f6f676c65617069732e636f6d2f7370656c6c2e6472697665722e44696374',
             response='0a1a313937302d30312d30312030303a30303a30302e303030303030')])


def test_exact_read_only_clock_packet_passes_without_mutating_evidence():
    row=captured();before=deepcopy(row)
    verify_read_only_rpc(row,1)
    assert row==before


@pytest.mark.parametrize('mutation',['write','request','response','error','missing','extra','unknown-field'])
def test_unexpected_clock_or_effect_packets_are_rejected(mutation):
    row=captured();call=row['rpc'][-1]
    if mutation=='write':call['path']='/spell.driver.SPELLDriverInterface_RSC/SetResource'
    elif mutation=='request':call['request']=''
    elif mutation=='response':call['response']=call['response'][:-2]+'31'
    elif mutation=='error':call['error']='failed'
    elif mutation=='missing':del call['response']
    elif mutation=='extra':row['rpc'].append(deepcopy(call))
    else:call['response']+='1001'
    with pytest.raises(AssertionError):verify_read_only_rpc(row,1)
