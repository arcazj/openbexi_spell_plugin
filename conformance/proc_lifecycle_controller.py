"""Retain native child metadata, reload and interpreter-lifetime observations."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import time
import traceback

sys.path.insert(0,'/opt/host')
from native import NativeSession
from children import ChildProcedures
from installed_provenance import capture
from proc_lifecycle_cases import CASES

ROOT=Path('/workspace')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(ROOT/'runtime.json').write_text(json.dumps(capture(),indent=2))
(ROOT/'host-inputs.json').write_text(json.dumps({p.name:sha(p) for p in Path('/opt/host').glob('*.py')}))
checks={}

for name,spec in CASES.items():
    project=ROOT/name.replace(':','-');project.mkdir()
    (project/'main.py').write_text(spec['source'])
    if 'child' in spec:(project/'child.py').write_text(spec['child'])
    (project/'plan.json').write_text(json.dumps({k:spec[k] for k in ('arguments','dimension','operation','rounds')}))
    (project/'evaluations.txt').write_text('0')
    session=NativeSession(project,project/'main.py',{})
    expression=("(__import__('pathlib').Path('evaluations.txt').write_text(str(int("
        "__import__('pathlib').Path('evaluations.txt').read_text())+1)),"+repr(spec['arguments'])+")[1]")
    if spec['operation']!='child':session.arguments=expression
    children=ChildProcedures(session.instance)
    events=[]
    row=dict(passed=False,dimension=spec['dimension'],operation=spec['operation'],
        commands=[],states=[],phases=[],source=spec['source'],expression=expression,
        procedure_inputs={p.name:sha(p) for p in project.glob('*.py')})

    def drain():
        while True:
            try:event=session.events.get_nowait()
            except queue.Empty:return
            events.append(event)
            if event.get('event') in {'connectionError','unsupportedRequest','childRequestRejected'}:
                raise RuntimeError(event)
            message=event.get('message',{})
            if message:
                children.observe(message)
                assert message['id']!='MSG_PROMPT',message

    def request(command,fields=None,**kwargs):
        row['commands'].append(dict(command=command,fields=fields or {},**kwargs))
        return session.request(command,fields,**kwargs)

    def wait_status(expected,procedure=None,allow_old_terminal=False):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            drain()
            if spec['operation']=='child':children.service(session)
            status=session.request('REQ_EXEC_STATUS',procedure=procedure)['ExecutorStatus']
            row['states'].append(dict(status=status,procedure=procedure or session.instance,monotonic=time.monotonic()))
            if status in expected:return status
            if status in {'ERROR','ABORTED'} and not allow_old_terminal:
                raise AssertionError((status,expected))
            time.sleep(.025)
        raise TimeoutError((name,expected,status))

    try:
        session.start();session.pump=drain
        for phase in range(1,spec['rounds']+1):
            wait_status({'PAUSED'},allow_old_terminal=phase>1)
            request('CMD_RUN',send=True)
            status=wait_status({'FINISHED','ERROR','ABORTED'})
            if spec['operation']=='child':
                assert status=='FINISHED',status
                opened={e['message']['fields']['ProcId'] for e in events
                    if e.get('message',{}).get('id')=='MSG_EXEC_OP'
                    and e['message']['fields'].get('ExecOp')=='OPEN'
                    and e['message']['fields'].get('ParentId')==session.instance}
                assert opened=={'child#1'},opened
                wait_status({'FINISHED'},'child#1')
                row['child_result']=json.loads((project/'child-result.json').read_bytes())
                row['parent_result']=json.loads((project/'parent-result.json').read_bytes())
                child=row['child_result']['initial'];parent=row['parent_result']['initial']
                assert child['NAME'] in opened and child['PARENT']==parent['NAME']==session.instance
                assert child['ARGS']==spec['arguments'] and parent['ARGS']=={}
                assert row['child_result']['custom']=={'owner':'child'}
                assert parent['PRIVATE_VALUE']=={'owner':'parent'}
                row['inventory']=session.request('REQ_EXEC_LIST',context=True)
                assert set(row['inventory']['ExecutorList'].split('\x03'))-{''}==opened|{session.instance}
            else:
                expected_error=(spec['dimension']=='failure' and phase==1 or
                    spec['dimension']=='recovery' and phase<3)
                assert status==('ERROR' if expected_error else 'FINISHED'),status
                runs=json.loads((project/'runs.json').read_bytes())
                assert len(runs)==phase and runs[-1]['phase']==phase
                evaluations=int((project/'evaluations.txt').read_text())
                expected_count=phase if spec['operation']=='reopen' else 1
                assert evaluations==runs[-1]['evaluations']==expected_count,(evaluations,runs)
                assert runs[-1]['initial']['ARGS']==spec['arguments']
                assert 'PRIVATE_VALUE' not in runs[-1]['initial']
                row['phases'].append(dict(phase=phase,status=status,evaluations=evaluations,observed=runs[-1]))
            if phase<spec['rounds']:
                if spec['operation']=='reload':request('CMD_RELOAD',send=True)
                else:
                    request('REQ_CLOSE_EXEC',context=True)
                    listing=request('REQ_EXEC_LIST',context=True)
                    assert session.instance not in listing['ExecutorList'].split('\x03'),listing
                    request('REQ_OPEN_EXEC',context=True,fields=dict(GuiMode='CONTROL',
                        Arguments=expression,OpenMode='{Automatic:True,Visible:True,Blocking:False}'))
        row['passed']=True
    except Exception:row['error']=traceback.format_exc()
    finally:
        if session.log:
            session.log.flush();session.log.seek(0)
            text=session.log.read();(project/'native.log').write_text(text)
            row['native_log_sha256']=sha(project/'native.log')
            if 'AddressSanitizer:' in text or 'runtime error:' in text:
                row.update(passed=False,sanitizer_error=True)
        try:session.close()
        except Exception:row.update(passed=False,cleanup_error=traceback.format_exc())
        (project/'events.json').write_text(json.dumps(events,indent=2))
        row['events_sha256']=sha(project/'events.json')
        checks[name]=row;(ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
        print(json.dumps(dict(case=name,passed=row['passed'],error=row.get('error'))),flush=True)
    if not row['passed']:break
raise SystemExit(set(checks)!=set(CASES) or not all(r['passed'] for r in checks.values()))
