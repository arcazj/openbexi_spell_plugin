"""Retain native ordering and failure observations without replacing child behavior."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import time
import traceback

sys.path.insert(0, '/opt/host')
from children import ChildProcedures
from native import NativeSession
from installed_provenance import capture
from child_modes_cases import CASES

ROOT=Path('/workspace')
(ROOT/'runtime.json').write_text(json.dumps(capture(),indent=2)+'\n')
(ROOT/'host-inputs.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(Path('/opt/host').glob('*.py'))},indent=2)+'\n')
checks={}
for name,spec in CASES.items():
    project=ROOT/name
    project.mkdir()
    (project/'main.py').write_text(spec['parent'])
    (project/'child.py').write_text(spec['child'])
    session=NativeSession(project,project/'main.py',{})
    children=ChildProcedures(session.instance)
    events=[]
    row=dict(passed=False, source=spec['parent'], child_source=spec['child'], observations=[])

    def drain():
        while True:
            try: event=session.events.get_nowait()
            except queue.Empty: return
            events.append(event)
            if event.get('event')=='connectionError': raise RuntimeError(event)
            if 'message' in event: children.observe(event['message'])

    def wait_for(predicate):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            drain()
            children.service(session)
            if predicate(): return
            time.sleep(.025)
        raise TimeoutError('Child mode condition: '+name)

    def instances():
        return {e['message']['fields']['ProcId'] for e in events
            if e.get('message',{}).get('id')=='MSG_EXEC_OP'
            and e['message']['fields'].get('ExecOp')=='OPEN'
            and e['message']['fields'].get('ParentId')==session.instance}

    def observe(child, phase):
        value={'phase':phase,'parent_status':session.request('REQ_EXEC_STATUS')['ExecutorStatus'],
               'child_status':session.request('REQ_EXEC_STATUS',procedure=child)['ExecutorStatus'],
               'child_started':(project/'child-started.txt').exists(),
               'parent_returned':(project/'parent-result.json').exists()}
        row['observations'].append(value)
        return value

    try:
        session.start()
        session.pump=drain
        session.request('CMD_RUN',send=True)
        wait_for(lambda:bool(instances()))
        child,=instances()
        row['child_instance']=child
        row['child_info']=session.request('REQ_EXEC_INFO',context=True,procedure=child)
        expected_mode='{Automatic:%s,Visible:True,Blocking:%s}' % (spec['automatic'],spec['blocking'])
        assert row['child_info']['OpenMode']==expected_mode
        if not spec['automatic']:
            wait_for(lambda:session.request('REQ_EXEC_STATUS',procedure=child)['ExecutorStatus']=='PAUSED')
            if not spec['blocking']: wait_for(lambda:(project/'parent-result.json').exists())
            for _ in range(3):
                state=observe(child,'before-manual-run')
                assert state['child_status']=='PAUSED' and not state['child_started']
                assert state['parent_returned'] is (not spec['blocking'])
                time.sleep(.075)
            session.request('CMD_RUN',send=True,procedure=child)
        if spec['hold']:
            wait_for(lambda:session.request('REQ_EXEC_STATUS',procedure=child)['ExecutorStatus']=='PROMPT')
            if not spec['blocking']: wait_for(lambda:(project/'parent-result.json').exists())
            for _ in range(3):
                state=observe(child,'child-awaiting-input')
                assert state['child_status']=='PROMPT' and state['child_started']
                assert state['parent_returned'] is (not spec['blocking'])
                time.sleep(.075)
            if spec['outcome']=='ABORTED':
                session.request('CMD_ABORT',send=True,procedure=child)
            else:
                session.request('MSG_ANSWER',{'ReturnValue':'continue'},send=True,procedure=child)
        wait_for(lambda:session.request('REQ_EXEC_STATUS',procedure=child)['ExecutorStatus']==spec['outcome'])
        wait_for(lambda:session.request('REQ_EXEC_STATUS')['ExecutorStatus'] in {'FINISHED','ERROR','ABORTED'})
        final=observe(child,'terminal')
        assert final['parent_status']=='FINISHED'
        row['parent_result']=json.loads((project/'parent-result.json').read_bytes())
        assert row['parent_result']==spec['expected_parent'],row['parent_result']
        row['inventory']=session.request('REQ_EXEC_LIST',context=True)
        assert set(filter(None,row['inventory']['ExecutorList'].split('\x03')))=={session.instance,child}
        assert (project/'child-result.txt').exists() is (spec['outcome']=='FINISHED')
        assert not any(e.get('event') in {'unsupportedRequest','childRequestRejected'} for e in events)
        row['passed']=True
    except Exception:
        row['error']=traceback.format_exc()
    finally:
        try: drain()
        except Exception: row.update(passed=False,drain_error=traceback.format_exc())
        if session.log:
            session.log.flush();session.log.seek(0)
            diagnostic=session.log.read()
            (project/'native.log').write_text(diagnostic)
            row['native_log_sha256']=hashlib.sha256((project/'native.log').read_bytes()).hexdigest()
            if 'AddressSanitizer:' in diagnostic or 'runtime error:' in diagnostic:
                row.update(passed=False,sanitizer_error=True)
        try: session.close()
        except Exception: row.update(passed=False,cleanup_error=traceback.format_exc())
        (project/'events.json').write_text(json.dumps(events,indent=2)+'\n')
        row['events_sha256']=hashlib.sha256((project/'events.json').read_bytes()).hexdigest()
        checks[name]=row
        (ROOT/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
        print(json.dumps({'case':name,'passed':row['passed'],'error':row.get('error')}),flush=True)
raise SystemExit(not all(row['passed'] for row in checks.values()))
