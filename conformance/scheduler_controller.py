"""Observe the actual native scheduler and its client IPC; never substitute it."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0,'/opt/host')
from native import NativeSession
sys.path.insert(0,'/workspace')
from installed_provenance import capture
integrated=capture()

results={}
for name,spec in json.loads(Path('/workspace/scenarios.json').read_text()).items():
    project=Path('/workspace')/name
    project.mkdir(exist_ok=True)
    (project/'main.py').write_text(spec['source'],encoding='utf-8')
    events,statuses=[],[]
    result=dict(passed=False,status=None)
    session=NativeSession(project,project/'main.py',{})
    def drain():
        while True:
            try:event=session.events.get_nowait()
            except queue.Empty:return
            event['received_monotonic']=time.monotonic()
            events.append(event)
            if event.get('event')=='connectionError':raise RuntimeError(event)
    try:
        session.start()
        session.pump=drain
        session.request('CMD_RUN',send=True)
        deadline=time.monotonic()+18
        while time.monotonic()<deadline:
            drain()
            status=session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
            if not statuses or statuses[-1]['status']!=status:
                statuses.append(dict(status=status,monotonic=time.monotonic()))
            if status in ('FINISHED','ERROR','ABORTED'):
                result['status']=status
                break
            time.sleep(.02)
        else:raise TimeoutError('Native scheduler scenario did not complete')
        drain()
        assert result['status']=='FINISHED',result['status']
        result['assertions']=json.loads((project/'assertions.json').read_text())
        if spec.get('waiting'):assert any(s['status']=='WAITING' for s in statuses),statuses
        if spec.get('no_waiting'):assert all(s['status']!='WAITING' for s in statuses),statuses
        messages=[e for e in events if e.get('message',{}).get('id')=='MSG_WRITE'
                  and e['message']['fields'].get('Text')==spec.get('message')]
        if 'message' in spec:
            assert len(messages)>=spec['minimum_messages'],len(messages)
            assert all(e['message']['fields']['Scope']=='1' for e in messages)
            for first,second in zip(messages,messages[1:]):
                assert second['received_monotonic']-first['received_monotonic']>=spec['minimum_spacing']
            countdown=[e for e in events if e.get('message',{}).get('fields',{}).get('ItemName')=='COUNTDOWN']
            assert countdown,'No actual remaining-time notification'
            fields=[e['message']['fields'] for e in countdown]
            remaining=[float(e['ItemValue']) for e in fields if e['ItemStatus']=='WAITING']
            assert remaining and all(value>0 for value in remaining),remaining
            assert all(a>=b for a,b in zip(remaining,remaining[1:])),remaining
            assert fields[-1]['ItemStatus']=='SUCCESS' and fields[-1]['ItemValue']=='0',fields[-1]
            result['countdown']=countdown
            result['messages']=messages
        result['passed']=True
    except Exception as error:
        result.update(error=type(error).__name__+': '+str(error))
    finally:
        try:drain()
        except Exception as error:result.update(passed=False,drain_error=str(error))
        if session.log:
            session.log.flush();session.log.seek(0)
            diagnostic=session.log.read()
            (project/'native.log').write_text(diagnostic,encoding='utf-8')
            if 'Exception in thread' in diagnostic:result.update(passed=False,thread_error=True)
        result['asrun']={str(p.relative_to(Path(session.directory.name))):p.read_text(errors='replace')
            for p in Path(session.directory.name).rglob('*') if p.is_file() and p.suffix.lower() in ('.asrun','.ar')}
        try:session.close()
        except Exception as error:result.update(passed=False,cleanup_error=str(error))
        result.update(events=events,statuses=statuses)
        results[name]=result
        Path('/workspace/observations.json').write_text(json.dumps(results,indent=2)+'\n')
        print(name,result['passed'],result.get('error',result['status']),flush=True)

site=Path('/usr/local/lib/python3.13/site-packages')
paths=[Path('/opt/host/native.py')]
for package in ('spell','spell_native'):
    paths += [p for p in (site/package).rglob('*') if p.is_file() and p.suffix in ('.py','.so')]
paths += [p for p in (site/'spell_native/bin').iterdir() if p.is_file()]
manifest=None
patch=Path('/opt/scheduler-native-patch')
if patch.exists():
    manifest=json.loads((patch/'manifest.json').read_text())
    for name,digest in manifest['artifacts'].items():
        assert hashlib.sha256((site/'spell_native/bin'/name).read_bytes()).hexdigest()==digest,name
    paths += [p for p in patch.rglob('*') if p.is_file() and 'runtime-bin' not in p.parts and 'compiled' not in p.parts]
Path('/workspace/runtime.json').write_text(json.dumps(dict(interpreter=sys.version,
    integrated=integrated,
    scheduler_manifest=manifest,
    installed={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2)+'\n')
