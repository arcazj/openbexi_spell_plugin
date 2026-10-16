"""Observe library selection and hidden modes without replacing native lookup."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import time
import traceback

sys.path[:0] = ['/opt/host','/workspace']
from children import ChildProcedures
from native import NativeSession
from installed_provenance import capture
from procedure_library_cases import CASES

ROOT = Path('/workspace')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
(ROOT/'runtime.json').write_text(json.dumps(capture(),indent=2))
(ROOT/'host-inputs.json').write_text(json.dumps({p.name:sha(p) for p in sorted(Path('/opt/host').glob('*.py'))}))
selected = json.loads((ROOT/'selected-cases.json').read_bytes())
checks = {}
for name,spec in CASES.items():
    if name not in selected:continue
    project = ROOT/name;project.mkdir()
    (project/'main.py').write_text(spec['parent'])
    for relative,source in spec['files'].items():
        path=project/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source)
    if spec['configuration'] is not None:
        (project/'spell-library.json').write_text(json.dumps(spec['configuration']))
    session=NativeSession(project,project/'main.py',{})
    children=ChildProcedures(session.instance)
    events=[];known={};manual_started=set()
    row=dict(passed=False,source=spec['parent'],files=spec['files'],configuration=spec['configuration'],
             inventories=[],child_info={},manual_observations=[],controls=[])

    def drain():
        while True:
            try:event=session.events.get_nowait()
            except queue.Empty:return
            events.append(event)
            if event.get('event')=='connectionError':raise RuntimeError(event)
            if 'message' in event:
                children.observe(event['message'])
                assert event['message']['id']!='MSG_PROMPT','Unexpected prompt'

    try:
        session.start();session.pump=drain
        session.request('CMD_RUN',send=True)
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            drain();children.service(session)
            listing=session.request('REQ_EXEC_LIST',context=True)
            inventory=set(filter(None,listing['ExecutorList'].split('\x03')))
            snapshot=sorted(inventory)
            if not row['inventories'] or row['inventories'][-1]!=snapshot:row['inventories'].append(snapshot)
            for instance in sorted(inventory-{session.instance}):
                if instance not in known:
                    info=session.request('REQ_EXEC_INFO',context=True,procedure=instance)
                    known[instance]=info;row['child_info'][instance]=info
                if not spec['automatic'] and instance not in manual_started:
                    status=session.request('REQ_EXEC_STATUS',procedure=instance)['ExecutorStatus']
                    if status!='PAUSED':continue
                    if not spec['blocking'] and not (project/'parent-result.json').exists():continue
                    for _ in range(3):
                        observed=dict(instance=instance,status=session.request('REQ_EXEC_STATUS',procedure=instance)['ExecutorStatus'],
                            child_started=(project/'child-started.json').exists(),parent_returned=(project/'parent-result.json').exists())
                        row['manual_observations'].append(observed)
                        assert observed['status']=='PAUSED' and not observed['child_started']
                        assert observed['parent_returned'] is (not spec['blocking'])
                        time.sleep(.075)
                    session.request('CMD_RUN',send=True,procedure=instance)
                    row['controls'].append(dict(instance=instance,command='CMD_RUN'));manual_started.add(instance)
            row['parent_status']=session.request('REQ_EXEC_STATUS')['ExecutorStatus']
            if row['parent_status'] in ('ERROR','ABORTED'):break
            if row['parent_status']=='FINISHED' and (project/'child-result.json').exists():break
            time.sleep(.025)
        drain()
        row['parent_status']=session.request('REQ_EXEC_STATUS')['ExecutorStatus']
        for key in ('parent-result','child-result','rejected'):
            path=project/(key+'.json')
            if path.exists():row[key.replace('-','_')]=json.loads(path.read_bytes())
        assert row['parent_status']=='FINISHED',row['parent_status']
        assert row.get('parent_result')==spec['expected_parent'],row.get('parent_result')
        assert row.get('child_result')==spec['expected_child'],row.get('child_result')
        assert ('rejected' in row) is spec['rejection']
        assert len(row['controls'])==int(not spec['automatic'])
        if known:
            expected='{Automatic:%s,Visible:%s,Blocking:%s}' % (spec['automatic'],spec['visible'],spec['blocking'])
            assert all(info['OpenMode']==expected for info in known.values())
        assert not any(e.get('event') in ('unsupportedRequest','childRequestRejected') for e in events)
        row['passed']=True
    except Exception:row['error']=traceback.format_exc()
    finally:
        try:drain()
        except Exception:row.update(passed=False,drain_error=traceback.format_exc())
        if session.log:
            session.log.flush();session.log.seek(0);log=session.log.read()
            (project/'native.log').write_text(log);row['native_log_sha256']=sha(project/'native.log')
            if 'AddressSanitizer:' in log or 'runtime error:' in log:row.update(passed=False,sanitizer_error=True)
        try:session.close()
        except Exception:row.update(passed=False,cleanup_error=traceback.format_exc())
        (project/'events.json').write_text(json.dumps(events,indent=2));row['events_sha256']=sha(project/'events.json')
        checks[name]=row;(ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
        print(json.dumps(dict(case=name,passed=row['passed'],error=row.get('error'))),flush=True)
raise SystemExit(not all(row['passed'] for row in checks.values()))
