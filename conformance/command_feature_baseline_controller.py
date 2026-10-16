"""Observe missing display behavior through real native helpers and binary DSS RPC."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
import uuid

sys.path[:0]=['/opt/host','/workspace/fixture','/workspace']
from native import NativeSession
from installed_provenance import capture
from command_feature_baseline_cases import CASES
from dss.local import create_servers
from openbexi_spell_dss.transport import Transport
from openbexi_spell_dss.journal import Journal
from openbexi_spell_dss.rpc import Dispatcher
from openbexi_spell_dss.server import Server

ROOT=Path('/workspace');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(ROOT/'runtime.json').write_text(json.dumps(capture(),indent=2))
(ROOT/'host-inputs.json').write_text(json.dumps({p.name:sha(p) for p in Path('/opt/host').glob('*.py')}))
checks={}
for name,spec in CASES.items():
    project=ROOT/name;project.mkdir()
    (project/'main.py').write_text(spec['source'])
    runtime,tcp,api=create_servers(project/'dss.sqlite',0)
    for endpoint in (tcp,api):threading.Thread(target=endpoint.serve_forever,daemon=True).start()
    transport=Transport('http://127.0.0.1:'+str(api.server_port),tcp.server_address)
    journal=Journal(project/'driver.sqlite');dispatcher=Dispatcher(transport,journal)
    identity=dict(session=uuid.uuid4().hex,procedure=uuid.uuid4().hex,definition=name,
        version='command-feature-baseline',controller_epoch=1,procedure_fence=1,mode='Development',release=None)
    calls=[];events=[]
    row=dict(passed=False,dimension=spec['dimension'],source=spec['source'],states=[],
        initial_ground=dispatcher.ground.state(),initial_dss=runtime.engine.state())
    def dispatch(path,raw):
        item=dict(path=path,request=raw.hex(),started=time.monotonic());calls.append(item)
        try:
            result=dispatcher.dispatch(path,raw,identity,uuid.uuid4().hex,lambda:None)
            item['response']=result.hex();return result
        except Exception as error:item['error']=repr(error);raise
        finally:item['elapsed']=time.monotonic()-item['started']
    server=Server(dispatch)
    session=NativeSession(project,project/'main.py',{},driver_port=server.port)
    def drain():
        while True:
            try:event=session.events.get_nowait()
            except queue.Empty:return
            events.append(event)
            assert event.get('event')!='connectionError',event
            assert event.get('message',{}).get('id')!='MSG_PROMPT','Unexpected interactive failure'
    try:
        session.start();session.pump=drain
        session.request('CMD_RUN',send=True);deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            drain();status=session.request('REQ_EXEC_STATUS')['ExecutorStatus']
            if not row['states'] or row['states'][-1]['status']!=status:
                row['states'].append(dict(status=status,monotonic=time.monotonic()))
            if status in ('FINISHED','ERROR','ABORTED'):break
            time.sleep(.01)
        drain();row['status']=status
        if (project/'observed.json').exists():row['observed']=json.loads((project/'observed.json').read_bytes())
        assert status=='FINISHED',status
        row['result']=json.loads((project/'result.json').read_bytes());row['passed']=True
    except Exception:row['error']=traceback.format_exc()
    finally:
        row['final_ground']=dispatcher.ground.state()
        row['final_dss']=runtime.engine.state()
        row['receipts']=runtime.engine.evidence(row['final_dss']['scenario_id'])['operations']
        if session.log:
            session.log.flush();session.log.seek(0);log=session.log.read()
            (project/'native.log').write_text(log);row['native_log_sha256']=sha(project/'native.log')
            if 'AddressSanitizer:' in log or 'runtime error:' in log:row.update(passed=False,sanitizer_error=True)
        try:session.close()
        except Exception:row.update(passed=False,cleanup_error=traceback.format_exc())
        server.close()
        for endpoint in (tcp,api):endpoint.shutdown();endpoint.server_close()
        transport.close();journal.close();runtime.engine.close()
        row['rpc']=calls
        (project/'events.json').write_text(json.dumps(events,indent=2));row['events_sha256']=sha(project/'events.json')
        checks[name]=row;(ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
        print(json.dumps(dict(case=name,passed=row['passed'],error=row.get('error'))),flush=True)
    # Cases are independent baselines, so retain all four counterexamples.
raise SystemExit(not all(row['passed'] for row in checks.values()))
