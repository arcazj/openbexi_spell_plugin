"""Observe genuine failed launches and recovery without changing native behavior."""
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
from child_start_cases import CASES

ROOT = Path('/workspace')
(ROOT/'runtime.json').write_text(json.dumps(capture(),indent=2)+'\n')
(ROOT/'host-inputs.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(Path('/opt/host').glob('*.py'))},indent=2)+'\n')
checks = {}
for name,spec in CASES.items():
    project = ROOT/name
    project.mkdir()
    (project/'main.py').write_text(spec['parent'])
    (project/'child.py').write_text(spec['child'])
    session = NativeSession(project,project/'main.py',{})
    children = ChildProcedures(session.instance)
    events = []
    row = dict(passed=False,source=spec['parent'],child_source=spec['child'],observations=[])

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
        raise TimeoutError('Child startup condition: '+name)

    def instances():
        return {e['message']['fields']['ProcId'] for e in events
            if e.get('message',{}).get('id')=='MSG_EXEC_OP'
            and e['message']['fields'].get('ExecOp')=='OPEN'
            and e['message']['fields'].get('ParentId')==session.instance}

    try:
        session.start()
        row['parent_instance']=session.instance
        session.pump=drain
        session.request('CMD_RUN',send=True)
        wait_for(lambda:(project/'failed-start.json').exists())
        row['rejection']=json.loads((project/'failed-start.json').read_bytes())
        assert row['rejection']['exception']=='DriverException' and row['rejection']['message']
        if spec['recovery']:
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
                    state={'child_status':session.request('REQ_EXEC_STATUS',procedure=child)['ExecutorStatus'],
                           'child_finished':(project/'child-finished.txt').exists(),
                           'parent_returned':(project/'parent-result.json').exists()}
                    row['observations'].append(state)
                    assert state['child_status']=='PAUSED' and not state['child_finished']
                    assert state['parent_returned'] is (not spec['blocking'])
                    time.sleep(.075)
                session.request('CMD_RUN',send=True,procedure=child)
            wait_for(lambda:session.request('REQ_EXEC_STATUS',procedure=child)['ExecutorStatus']=='FINISHED')
            row['child_status']=session.request('REQ_EXEC_STATUS',procedure=child)['ExecutorStatus']
            assert (project/'child-finished.txt').read_text()=='finished'
        wait_for(lambda:session.request('REQ_EXEC_STATUS')['ExecutorStatus'] in {'FINISHED','ERROR','ABORTED'})
        row['parent_status']=session.request('REQ_EXEC_STATUS')['ExecutorStatus']
        assert row['parent_status']=='FINISHED'
        row['result']=json.loads((project/'parent-result.json').read_bytes())
        assert row['result']==spec['expected']
        row['inventory']=session.request('REQ_EXEC_LIST',context=True)
        expected={session.instance}|({child} if spec['recovery'] else set())
        assert set(filter(None,row['inventory']['ExecutorList'].split('\x03')))==expected
        assert len(instances())==int(spec['recovery'])
        assert not any(e.get('event') in {'unsupportedRequest','childRequestRejected'} for e in events)
        row['passed']=True
    except Exception:
        row['error']=traceback.format_exc()
    finally:
        try: drain()
        except Exception: row.update(passed=False,drain_error=traceback.format_exc())
        if session.log:
            session.log.flush(); session.log.seek(0)
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
