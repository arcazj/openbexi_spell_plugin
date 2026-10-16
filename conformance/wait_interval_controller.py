"""Observe actual timed progress messages without replacing the native clock."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import time
import traceback

sys.path.insert(0,'/opt/host')
from native import NativeSession
from installed_provenance import capture
from wait_interval_cases import CASES

ROOT=Path('/workspace')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(ROOT/'runtime.json').write_text(json.dumps(capture(),indent=2))
(ROOT/'host-inputs.json').write_text(json.dumps({p.name:sha(p) for p in Path('/opt/host').glob('*.py')}))
checks={}
for name,spec in CASES.items():
    project=ROOT/name.replace(':','-');project.mkdir()
    (project/'main.py').write_text(spec['source'])
    (project/'plan.json').write_text(json.dumps({k:v for k,v in spec.items() if k!='source'}))
    session=NativeSession(project,project/'main.py',{})
    events=[]
    row=dict(passed=False,source=spec['source'],dimension=spec['dimension'],states=[])

    def drain():
        while True:
            try:event=session.events.get_nowait()
            except queue.Empty:return
            event['received_monotonic']=time.monotonic();events.append(event)
            assert event.get('event')!='connectionError',event
            assert event.get('message',{}).get('id')!='MSG_PROMPT',event

    try:
        session.start();session.pump=drain
        session.request('CMD_RUN',send=True)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            drain();status=session.request('REQ_EXEC_STATUS')['ExecutorStatus']
            if not row['states'] or row['states'][-1]['status']!=status:
                row['states'].append(dict(status=status,monotonic=time.monotonic()))
            if status in {'FINISHED','ERROR','ABORTED'}:break
            time.sleep(.01)
        drain();row['status']=status
        assert status=='FINISHED',status
        result=row['result']=json.loads((project/'result.json').read_bytes())
        assert len(result['rejected'])==int(spec['dimension'] in ('failure','recovery'))
        progress=[e for e in events if e.get('message',{}).get('fields',{}).get('Text')==spec['message']]
        countdown=[e for e in events if e.get('message',{}).get('fields',{}).get('ItemName')=='COUNTDOWN'
            and e['message']['fields'].get('ItemStatus')=='WAITING']
        row['progress']=progress;row['countdown']=countdown
        if spec['waiting']:
            assert any(r['status']=='WAITING' for r in row['states'])
            assert result['returned'] is True
            assert spec['duration']<=result['ended']-result['started']<spec['duration']+1
        if spec['dimension'] in ('boundary','failure'):
            assert not progress,progress
        else:
            times=[e['received_monotonic'] for e in progress]
            row['progress_offsets']=[t-result['started'] for t in times]
            gaps=[b-a for a,b in zip([result['started'],*times],times)]
            row['progress_gaps']=gaps
            if spec['family']=='simple':
                assert len(gaps)==3,gaps
                assert all(.95<=gap<1.3 for gap in gaps),gaps
            else:
                assert len(gaps) in (4,5),gaps
                expected=[3,1,1,.4,.4]
                assert all(wanted-.05<=actual<wanted+.3 for wanted,actual in zip(expected,gaps)),gaps
            for event in progress:
                assert result['started']<=event['received_monotonic']<=result['ended']+.1
                assert any(abs(c['received_monotonic']-event['received_monotonic'])<.35 for c in countdown)
            assert len({c['message']['fields']['ItemValue'] for c in countdown})>=3
        row['passed']=True
    except Exception:row['error']=traceback.format_exc()
    finally:
        if session.log:
            session.log.flush();session.log.seek(0)
            text=session.log.read();(project/'native.log').write_text(text)
            row['native_log_sha256']=sha(project/'native.log')
            if 'AddressSanitizer:' in text or 'runtime error:' in text:row.update(passed=False,sanitizer_error=True)
        try:session.close()
        except Exception:row.update(passed=False,cleanup_error=traceback.format_exc())
        (project/'events.json').write_text(json.dumps(events,indent=2));row['events_sha256']=sha(project/'events.json')
        checks[name]=row;(ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
        print(json.dumps(dict(case=name,passed=row['passed'],error=row.get('error'))),flush=True)
    if not row['passed']:break
raise SystemExit(set(checks)!=set(CASES) or not all(r['passed'] for r in checks.values()))
