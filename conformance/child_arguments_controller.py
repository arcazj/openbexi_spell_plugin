"""Observe actual parent/child execution, argument values, inventory and cleanup."""
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
from child_arguments_cases import CASES

ROOT = Path('/workspace')
(ROOT/'runtime.json').write_text(json.dumps(capture(),indent=2)+'\n')
(ROOT/'host-inputs.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(Path('/opt/host').glob('*.py'))},indent=2)+'\n')
checks = {}
for name,spec in CASES.items():
    project = ROOT/name.replace(':','-')
    project.mkdir()
    (project/'main.py').write_text(spec['parent'])
    (project/'child.py').write_text(spec['child'])
    session = NativeSession(project,project/'main.py',{})
    children = ChildProcedures(session.instance)
    events = []
    pending_prompts = []
    row = {key:spec[key] for key in ('dimension','contracts','oracle')}
    row.update(passed=False,source=spec['parent'],child_source=spec['child'],prompts=[],replies=[])

    def drain():
        while True:
            try:
                event = session.events.get_nowait()
            except queue.Empty:
                return
            events.append(event)
            if event.get('event') == 'connectionError':
                raise RuntimeError(event)
            if 'message' in event:
                children.observe(event['message'])
                if event['message']['id']=='MSG_PROMPT':
                    fields=event['message']['fields']
                    row['prompts'].append(fields)
                    pending_prompts.append(fields)

    try:
        session.start()
        session.pump = drain
        session.request('CMD_RUN',send=True)
        deadline = time.monotonic()+20
        status = None
        while time.monotonic()<deadline:
            drain()
            children.service(session)
            while pending_prompts:
                fields=pending_prompts.pop(0)
                assert spec['reply'] is not None and not row['replies'],'Unexpected or repeated prompt'
                assert "does not contain variable 'MISSING'" in fields['Text']
                assert fields['ProcId'] in children.children,'Prompt did not come from the child'
                session.request('MSG_ANSWER',{'ReturnValue':spec['reply']},send=True,procedure=fields['ProcId'])
                row['replies'].append({'procedure':fields['ProcId'],'answer':spec['reply']})
            status = session.request('REQ_EXEC_STATUS')['ExecutorStatus']
            if status in {'FINISHED','ERROR','ABORTED'}:
                break
            time.sleep(.025)
        drain()
        row['parent_status'] = status
        assert status == 'FINISHED',status
        instances = {e['message']['fields']['ProcId'] for e in events
            if e.get('message',{}).get('id') == 'MSG_EXEC_OP'
            and e['message']['fields'].get('ExecOp') == 'OPEN'
            and e['message']['fields'].get('ParentId') == session.instance}
        row['child_instances'] = sorted(instances)
        assert len(instances) == spec['expected_children'],instances
        assert len(row['prompts'])==len(row['replies'])==int(spec['reply'] is not None)
        row['inventory'] = session.request('REQ_EXEC_LIST',context=True)
        inventory = set(filter(None,row['inventory']['ExecutorList'].split('\x03')))
        assert inventory == {session.instance,*instances},inventory
        row['child_statuses'] = {child:session.request('REQ_EXEC_STATUS',procedure=child)['ExecutorStatus']
                                 for child in instances}
        assert all(status=='FINISHED' for status in row['child_statuses'].values())
        row['parent_result'] = json.loads((project/'parent-result.json').read_bytes())
        assert row['parent_result'] == spec['expected_parent']
        if spec['expected_children']:
            row['child_result'] = json.loads((project/'child-result.json').read_bytes())
            assert row['child_result'] == spec['expected_child']
        else:
            assert not (project/'child-result.json').exists()
        assert not any(e.get('event') in {'unsupportedRequest','childRequestRejected'} for e in events)
        row['passed'] = True
    except Exception:
        row['error'] = traceback.format_exc()
    finally:
        try:
            drain()
        except Exception:
            row.update(passed=False,drain_error=traceback.format_exc())
        if session.log:
            session.log.flush()
            session.log.seek(0)
            (project/'native.log').write_text(session.log.read())
            row['native_log_sha256'] = hashlib.sha256((project/'native.log').read_bytes()).hexdigest()
        try:
            session.close()
        except Exception:
            row.update(passed=False,cleanup_error=traceback.format_exc())
        (project/'events.json').write_text(json.dumps(events,indent=2)+'\n')
        row['events_sha256'] = hashlib.sha256((project/'events.json').read_bytes()).hexdigest()
        checks[name] = row
        (ROOT/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
        print(json.dumps({'case':name,'passed':row['passed'],'error':row.get('error')}),flush=True)
raise SystemExit(not all(row['passed'] for row in checks.values()))
