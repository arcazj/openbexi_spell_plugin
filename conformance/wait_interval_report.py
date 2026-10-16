"""Qualify interval progression from retained clocks, messages and native states."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from wait_interval_cases import CASES
from installed_provenance import verify_capture

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution'))
from run_language_regressions import validate_report

CONTRACTS=['CMP-LRM244-'+name for name in (
    'EXAMPLE-082','EXAMPLE-083','MODIFIER-INTERVAL','SECTION-4-6-5-069')]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())


def qualify(path,image):
    raw=read(path)
    validate_report(path,image,len(CASES))
    assert raw['passed'] and not raw['timed_out'] and set(raw['checks'])==set(CASES)
    verify_capture(raw['runtime_sources']['integrated'],raw['inputs'])
    assert raw['host_inputs']=={p.name:sha(p) for p in (ROOT/'host_runtime/python').glob('*.py')}
    workspace=path.parent/'workspace'
    assert read(workspace/'checks.json')==raw['checks']
    for name in ('wait_interval_cases.py','wait_interval_controller.py','installed_provenance.py'):
        assert sha(workspace/name)==raw['inputs']['conformance/'+name]
    checks=deepcopy(raw['checks'])
    for name,spec in CASES.items():
        row=checks[name];project=workspace/name.replace(':','-')
        assert row['passed'] and not any(k.endswith('_error') for k in row)
        assert row['source']==spec['source'] and row['dimension']==spec['dimension']
        assert (project/'main.py').read_text()==spec['source']
        assert read(project/'plan.json')=={k:v for k,v in spec.items() if k!='source'}
        result=read(project/'result.json');assert result==row['result']
        assert sha(project/'events.json')==row['events_sha256']
        assert sha(project/'native.log')==row['native_log_sha256']
        log=(project/'native.log').read_text()
        assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
        events=read(project/'events.json')
        assert not any(e.get('event')=='connectionError' or
            e.get('message',{}).get('id')=='MSG_PROMPT' for e in events)
        progress=[e for e in events if e.get('message',{}).get('fields',{}).get('Text')==spec['message']]
        countdown=[e for e in events if e.get('message',{}).get('fields',{}).get('ItemName')=='COUNTDOWN'
            and e['message']['fields'].get('ItemStatus')=='WAITING']
        assert progress==row['progress'] and countdown==row['countdown']
        assert row['status']=='FINISHED' and row['states'][-1]['status']=='FINISHED'
        assert not {'ERROR','ABORTED'} & {r['status'] for r in row['states']}
        assert len(result['rejected'])==int(spec['dimension'] in ('failure','recovery'))
        assert all(error in ('SyntaxException','DriverException') for error in result['rejected'])
        if spec['waiting']:
            assert read(project/'ready.json')=={'started':result['started']}
            assert result['returned'] is True
            assert spec['duration']<=result['ended']-result['started']<spec['duration']+1
            assert any(r['status']=='WAITING' for r in row['states'])
        if spec['dimension'] in ('boundary','failure'):
            assert not progress
        else:
            times=[e['received_monotonic'] for e in progress]
            gaps=[b-a for a,b in zip([result['started'],*times],times)]
            assert row['progress_offsets']==[t-result['started'] for t in times]
            assert row['progress_gaps']==gaps
            expected=[1,1,1] if spec['family']=='simple' else [3,1,1,.4,.4]
            assert len(gaps) in ((3,) if spec['family']=='simple' else (4,5))
            assert all(wanted-.05<=actual<wanted+.3 for wanted,actual in zip(expected,gaps))
            for event in progress:
                assert result['started']<=event['received_monotonic']<=result['ended']+.1
                assert any(abs(c['received_monotonic']-event['received_monotonic'])<.35 for c in countdown)
            assert len({c['message']['fields']['ItemValue'] for c in countdown})>=3
        row.update(contracts=[],oracle='LRM pp58-59; retained real-clock timestamps, actual progress/countdown IPC and native status. Missing progress Message must fail.')
    for dimension in ('positive','boundary','failure','recovery'):
        dependencies=[key for key,spec in CASES.items() if spec['dimension']==dimension]
        assert len(dependencies)==2
        checks['intervals:'+dimension]=dict(passed=True,dimension=dimension,contracts=CONTRACTS,
            dependencies=dependencies,oracle='Scalar and staged interval leaves must both pass independently; scheduler uses its original 200ms real-clock tick.')
    inputs=dict(raw['inputs'])
    for name in ('conformance/wait_interval_report.py','tests/test_wait_interval_report.py'):
        inputs[name]=sha(ROOT/name)
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,
        qualified_contracts=CONTRACTS,raw=dict(path=str(path.resolve()),sha256=sha(path)),
        scope='Simple and staged WaitFor progress intervals with actual native countdown and message events',
        exclusions=['Full WaitFor function','Other WaitFor modifiers','Long-duration clock drift'],
        full_v05_accepted=False,full_v06_accepted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path);parser.add_argument('--image',required=True)
    args=parser.parse_args();report=qualify(args.raw,args.image)
    path=ROOT/'conformance/evidence/wait_interval.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(path),contracts=len(CONTRACTS),checks=len(report['checks']))))


if __name__=='__main__':main()
