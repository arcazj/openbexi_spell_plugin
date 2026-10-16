"""Require independent clocks, native states and held TM/countdown observations."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from wait_control_cases import CASES
from installed_provenance import verify_capture

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution'))
from run_language_regressions import validate_report
from evidence_sources import source_bytes

CONTRACTS=[
    'CMP-LRM244-CONTROL-WAITFOR-INTERRUPT', 'CMP-LRM244-CONTROL-WAITFOR-SKIP',
    'CMP-LRM244-CONTROL-WAITFOR-STEP', 'CMP-LRM244-OUTCOME-WAIT-ABORT',
    'CMP-LRM244-SECTION-4-6-4-068', 'CMP-LRM244-STATE-WAITFOR-INTERRUPTED',
    'CMP-LRM244-STATE-WAITFOR-PAUSE', 'CMP-LRM244-STATE-WAITFOR-WAITING',
]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def qualify(path,image,source_revision=None):
    raw=json.loads(path.read_bytes())
    validate_report(path,image,len(CASES),source_revision=source_revision)
    assert raw['passed'] and not raw['timed_out'] and set(raw['checks'])==set(CASES)
    diagnostic=raw.get('diagnostic_overlay',False)
    if diagnostic:
        from wait_interrupt_provenance import qualification_identity
        assert qualification_identity(raw['runtime_sources'],raw['inputs'])==raw['qualification_identity']
    else:
        assert source_revision is None, 'Fresh qualification must use current source inputs'
        verify_capture(raw['runtime_sources']['integrated'],raw['inputs'])
        from composed_diagnostic_proof import verify_donor
        donor=verify_donor(raw['runtime_sources']['integrated'],'wait_interrupt')
    assert raw['host_inputs']=={p.name:sha(p) for p in (ROOT/'host_runtime/python').glob('*.py')}
    workspace=path.parent/'workspace'
    assert json.loads((workspace/'checks.json').read_bytes())==raw['checks']
    for name,digest in raw['inputs'].items():
        if name.startswith('src/dss/'):
            assert sha(workspace/'fixture'/name.removeprefix('src/'))==digest,name
    for name in ('wait_control_cases.py','wait_control_controller.py','installed_provenance.py'):
        if diagnostic and name=='wait_control_controller.py':
            expected=source_bytes(ROOT,'conformance/'+name,source_revision).replace(
                b'from installed_provenance import capture',b'from wait_interrupt_provenance import capture')
            assert (workspace/name).read_bytes()==expected
        else:
            assert sha(workspace/name)==raw['inputs']['conformance/'+name]
    if diagnostic:
        for name,digest in raw['generated_sources'].items():assert sha(workspace/name)==digest
    checks=deepcopy(raw['checks'])
    for name,spec in CASES.items():
        row=checks[name]
        assert row['passed'] and not any(key.endswith('_error') for key in row)
        assert row['source']==spec['source'] and row['dimension']==spec['dimension']
        project=workspace/name.replace(':','-')
        assert (project/'main.py').read_text()==spec['source']
        plan=json.loads((project/'plan.json').read_bytes())
        assert all(plan[k]==spec[k] for k in ('kind','action','dimension'))
        for filename,key in (('ready.json','ready'),('returned.json','returned'),('finished.json','recovery')):
            assert json.loads((project/filename).read_bytes())==row[key]
        for filename,key in (('events.json','events_sha256'),('native.log','native_log_sha256')):
            assert sha(project/filename)==row[key]
        events=json.loads((project/'events.json').read_bytes())
        log=(project/'native.log').read_text()
        assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
        states=[x['status'] for x in row['states']]
        assert states[0]=='PAUSED' and states[-1]=='FINISHED'
        for expected in ('WAITING','INTERRUPTED','PAUSED'):
            assert expected in states
        assert not {'ERROR','ABORTED'} & set(states)
        held=row['held'];assert held['until']-held['since']>=.5
        held_states=[x['status'] for x in row['states'] if held['since']<=x['monotonic']<=held['until']]
        assert len(held_states)>=3 and set(held_states)=={'INTERRUPTED'}
        assert not any(e.get('message',{}).get('fields',{}).get('ItemName')=='COUNTDOWN'
            and held['since']<=e['received_monotonic']<=held['until'] for e in events)
        acquisitions=[x for x in row['rpc'] if x['path'].endswith('/RefreshItem')]
        assert not any(held['since']<=x['started']<=held['until'] for x in acquisitions)
        actions=row['actions']
        expected=['CMD_RUN','CMD_INTERRUPT']
        if spec['dimension']=='failure':expected+=['CMD_INTERRUPT']
        expected+=['CMD_STEP' if spec['action']=='step' else 'CMD_SKIP','CMD_RUN']
        assert [x['command'] for x in actions]==expected
        control=actions[-2]
        assert held['until']<=control['monotonic']<=actions[-1]['monotonic']
        assert row['paused_at']>=control['epoch']
        paused_states=[x['status'] for x in row['states'] if control['monotonic']<=x['monotonic']<actions[-1]['monotonic']]
        assert paused_states[-3:]==['PAUSED']*3
        assert row['returned']['value'] is True
        assert .35<=row['recovery']['recovery_elapsed']<2
        assert len(row['ready']['rejected'])==(1 if spec['dimension']=='failure' else 0)
        if spec['action']=='skip':assert row['paused_at']<control['epoch']+1
        if spec['kind']!='telemetry' and spec['action']=='step':
            target=row['ready']['target']
            assert target<=row['paused_at']<=max(target,control['epoch'])+1
            if spec['dimension']=='boundary':assert control['epoch']>=target+.4
        if spec['kind']=='telemetry':
            assert held['acquisitions']>=2
            if spec['action']=='step':
                assert len(acquisitions)>held['acquisitions']
                assert row['last_tm_value']==plan['expected_tick']
                assert row['returned']['monotonic']>=row['condition_satisfied_at']
            else:assert len(acquisitions)==held['acquisitions']
        row.update(contracts=[],oracle='Actual native IPC control/state observations, independent UTC/monotonic clocks, original binary TM reads and controlled DSS publication; LRM pp57-58.')
    for dimension in ('positive','boundary','failure','recovery'):
        dependencies=[key for key,spec in CASES.items() if spec['dimension']==dimension]
        assert len(dependencies)==6
        checks['interrupt-controls:'+dimension]=dict(passed=True,dimension=dimension,
            contracts=[] if diagnostic else CONTRACTS,dependencies=dependencies,
            oracle='All relative, absolute and telemetry STEP/SKIP leaves must independently pass this dimension. PAUSE in the manual maps to native IPC PAUSED.')
    inputs=dict(raw['inputs'])
    for name in ('conformance/wait_control_report.py','tests/test_wait_control_report.py'):
        inputs[name]=sha(ROOT/name)
    if not diagnostic:
        inputs['conformance/composed_diagnostic_proof.py']=sha(ROOT/'conformance/composed_diagnostic_proof.py')
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,
        diagnostic_donor=None if diagnostic else donor,
        qualified_contracts=[] if diagnostic else CONTRACTS,candidate_contracts=CONTRACTS if diagnostic else [],
        raw=dict(path=str(path.resolve()),sha256=sha(path)),
        scope='LRM pp57-58 interruption, resumption and cancellation of time and telemetry waits',
        exclusions=['Full WaitFor function','Complete telemetry verification/modifier surface','Interval progression'],
        full_v05_accepted=False,full_v06_accepted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path);parser.add_argument('--image',required=True)
    args=parser.parse_args();report=qualify(args.raw,args.image)
    path=ROOT/'conformance/evidence/wait_control.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(path),contracts=len(CONTRACTS),checks=len(report['checks']))))


if __name__=='__main__':main()
