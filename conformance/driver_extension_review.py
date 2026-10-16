"""Verify actual driver RESUME hooks and no replay of completed DSS commands."""
import ast
from collections import Counter
import hashlib,json
from pathlib import Path
import sys
from aggregate_support import ROOT,sha,read,ref
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'driver_plugin/src')]
from dss.packets import decode_tc
from evidence_database import evidence_database
from driver_extension_cases import CASES
from limit_telemetry_sources import verify
from run_language_regressions import validate_report

STAGES=('TRANSPORT','LOADING','RELEASE','ACKNOWLEDGEMENT','ONBOARD_EXECUTION')
OUTCOMES=('ACCEPTED','LOADED','RELEASED','ACKNOWLEDGED','SUCCEEDED')


def review(path,image,native_wheel,driver_wheel):
    validate_report(path,image,4);raw=read(path);workspace=path.parent/'workspace'
    assert raw['passed'] and not raw['timed_out'] and raw['controller_exit_code']==0
    assert set(raw['checks'])==set(CASES)
    assert read(workspace/'checks.json')==raw['checks']
    assert raw['artifacts']=={p.relative_to(workspace).as_posix():sha(p) for p in workspace.rglob('*') if p.is_file()}
    assert raw['host_inputs']=={p.name:sha(p) for p in (ROOT/'host_runtime/python').glob('*.py')}
    wheels=verify(raw,native_wheel,driver_wheel,profile='fresh-composed-display-command-wheel/1')
    checks={}
    for name,row in raw['checks'].items():
        dimension=name.split(':')[1];spec=CASES[name];project=workspace/name.replace(':','__')
        assert row['passed'] and row['status']=='FINISHED' and row['states'][-1]['status']=='FINISHED'
        assert row['source']==spec['source']==(project/'main.py').read_text(encoding='utf-8')
        assert row['result']==read(project/'result.json')=={'completed':True}
        assert row['observed']==read(project/'observed.json')
        expected=['CMD1'] if dimension=='failure' else ['CMD1','CMD2','CMD3']
        assert row['initial_dss']['core']['commands_executed']==0
        assert row['final_dss']['core']['commands_executed']==len(expected)
        sends=[call for call in row['observed']['calls'] if call['function']=='Send']
        wanted=[False,True] if dimension=='recovery' else [dimension!='failure']
        assert [(call['return_type'],ast.literal_eval(call['returned'])) for call in sends]==[('bool',v) for v in wanted]
        hooks=row['observed']['driver']
        assert [r['name'] for r in hooks if r['action']=='command-completed']==expected
        assert [r['action'] for r in hooks if r['action'] in ('before','perform','after')]==['before','perform','after']
        assert all(r['code']=='Z' for r in hooks if r['action'] in ('before','perform','after'))
        assert sum(r['action']=='driver-interruption' for r in hooks)==1
        answer,=row['answers'];assert answer['selected']=='Z'
        assert answer['choices']==(['Q','Z'] if dimension=='boundary' else ['Z'])
        events=read(project/'events.json');assert sha(project/'events.json')==row['events_sha256']
        assert [e['message']['fields'] for e in events if e.get('message',{}).get('id')=='MSG_PROMPT']==[answer['fields']]
        assert sha(project/'native.log')==row['native_log_sha256']
        with evidence_database(project/'dss.sqlite') as db:
            saved=db.execute('SELECT request_hash,raw_tc,acknowledgement FROM operations ORDER BY rowid').fetchall()
        assert len(saved)==len(row['receipts'])==5*len(expected)
        commands=[];operations=[]
        for index,((digest,packet,encoded),receipt) in enumerate(zip(saved,row['receipts'])):
            ack=json.loads(encoded);frame=decode_tc(packet)
            assert digest==receipt['request_hash'] and packet.hex()==receipt['packet_hex']
            assert hashlib.sha256(packet).hexdigest()==receipt['packet_sha256'] and ack==receipt['acknowledgement']
            assert frame['stage']==ack['stage']==STAGES[index%5] and ack['outcome']==OUTCOMES[index%5]
            assert frame['operation_id']==ack['operation_id'] and receipt['ingress_delivery_count']==1
            if index%5==0:commands.append(frame['command_name']);operations.append(frame['operation_id'])
        assert commands==expected and len(set(operations))==len(expected)
        checks[name]=dict(passed=True,dimension=dimension,contracts=[],completed_commands=commands,
            oracle='Explicit extension hooks execute in before/perform/after order; original Send returns actual action result; immutable DSS packets and receipts show each completed command exactly once, including rejection and later continuation.')
    inputs=dict(raw['inputs']);inputs['conformance/driver_extension_review.py']=sha(ROOT/'conformance/driver_extension_review.py')
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,raw=ref(path),composed_wheels=wheels,
        full_v05_accepted=False,scope='LRM p116 extension point with an explicitly installed fixture driver. GENERIC does not provide an implicit RESUME implementation.')
