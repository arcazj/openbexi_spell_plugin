"""Observe remaining command behavior through real native helpers and binary DSS RPC."""
import hashlib
import os
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
from command_catalog_provenance import capture
if os.environ.get('OPENBEXI_CONFORMANCE_COMPOSED') == '1':
    from installed_provenance import capture_application as capture
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
from command_catalog_cases import CASES
from dss.local import create_servers
from openbexi_spell_dss.transport import Transport
from openbexi_spell_dss.journal import Journal
from openbexi_spell_dss.rpc import Dispatcher
from openbexi_spell_dss.server import Server

ROOT=Path('/workspace');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(ROOT/'runtime.json').write_text(json.dumps(capture(),indent=2))
(ROOT/'host-inputs.json').write_text(json.dumps({p.name:sha(p) for p in Path('/opt/host').glob('*.py')}))
checks={}
selected=json.loads((ROOT/'selected-cases.json').read_bytes())
CASES={name:spec for name,spec in CASES.items() if name in selected}
for name,spec in CASES.items():
    project=ROOT/name.replace(':','-');project.mkdir()
    (project/'main.py').write_text(spec['source'])
    runtime,tcp,api=create_servers(project/'dss.sqlite',0)
    for endpoint in (tcp,api):threading.Thread(target=endpoint.serve_forever,daemon=True).start()
    transport=Transport('http://127.0.0.1:'+str(api.server_port),tcp.server_address)
    journal=Journal(project/'driver.sqlite');dispatcher=Dispatcher(transport,journal)
    identity=dict(session=uuid.uuid4().hex,procedure=uuid.uuid4().hex,definition=name,
        version='command-catalog-candidate',controller_epoch=1,procedure_fence=1,mode='Development',release=None)
    calls=[];events=[];clock_observations=[];last_tick=0;prompts=[];pending=[]
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
            if event.get('message',{}).get('id')=='MSG_PROMPT':pending.append(event['message'])
    try:
        session.start();session.pump=drain
        session.request('CMD_RUN',send=True);deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            drain();status=session.request('REQ_EXEC_STATUS')['ExecutorStatus']
            while pending:
                fields=pending.pop(0)['fields']
                choices=fields.get('ExpectedValues','').split('\x04')
                assert choices==['O','C'] and 'Confirm critical command execution:' in fields['Text'],fields
                assert len(prompts)<len(spec['prompt_answers']),fields
                state=runtime.engine.state()
                operations=runtime.engine.evidence(state['scenario_id'])['operations']
                assert not operations and state['core']['commands_executed']==0
                answer=spec['prompt_answers'][len(prompts)]
                prompts.append(dict(fields=fields,answer=answer,before_dss=state,before_operations=operations))
                session.request('MSG_ANSWER',{'ReturnValue':str(choices.index(answer))},send=True)
            active_calls=[call for call in calls if call['path'].endswith('_TC/SendCommand') and 'elapsed' not in call]
            if active_calls and time.monotonic()-last_tick>=.1:
                active=active_calls[-1]
                options=unpack(p.CommandDesc.FromString(bytes.fromhex(active['request'])).config)
                state=runtime.engine.state()
                operations=runtime.engine.evidence(state['scenario_id'])['operations']
                # A future onboard tag must already be released before the
                # independent controller advances simulation time. Ground
                # holds instead advance with no transmitted command packet.
                ready='Time' not in options or len(operations)>=4
                if ready:
                    clock_observations.append(dict(rpc_request=active['request'],before=state,
                        stages=[row['acknowledgement']['stage'] for row in operations]))
                    runtime.engine.control('STEP',state['epoch'],state['revision'],1)
                    last_tick=time.monotonic()
            if not row['states'] or row['states'][-1]['status']!=status:
                row['states'].append(dict(status=status,monotonic=time.monotonic()))
            if status in ('FINISHED','ERROR','ABORTED'):break
            time.sleep(.01)
        drain();row['status']=status
        if (project/'observed.json').exists():row['observed']=json.loads((project/'observed.json').read_bytes())
        assert status=='FINISHED',status
        row['result']=json.loads((project/'result.json').read_bytes())
        state=runtime.engine.state()
        operations=runtime.engine.evidence(state['scenario_id'])['operations']
        assert state['core']['commands_executed']==spec['expected_executions'],state
        assert len(operations)==spec['expected_stages'],operations
        assert [r['acknowledgement']['command_name'] for r in operations if r['acknowledgement']['stage']=='TRANSPORT']==spec['expected_members']
        assert [r['answer'] for r in prompts]==spec['prompt_answers']
        if name.startswith('SequenceLoadOnly:'):
            assert [r['acknowledgement']['stage'] for r in operations]==['TRANSPORT','LOADING']*3
            runtime.engine.control('STEP',state['epoch'],state['revision'],10)
            assert runtime.engine.state()['core']['commands_executed']==0
        if name.startswith('LoadOnly:') and spec['expected_stages']==2:
            assert [r['acknowledgement']['stage'] for r in operations]==['TRANSPORT','LOADING']
            runtime.engine.control('STEP',state['epoch'],state['revision'],10)
            assert runtime.engine.state()['core']['commands_executed']==0
        if name.startswith('Time:') and name.split(':')[1] in ('positive','recovery','encoding'):
            assert any(r['stages']==['TRANSPORT','LOADING','RELEASE','ACKNOWLEDGEMENT']
                       and r['before']['core']['commands_executed']==0 for r in clock_observations)
        if name.startswith(('ReleaseTime:','SendDelay:')) and name.split(':')[1] in ('positive','recovery','encoding'):
            assert any(r['stages']==[] for r in clock_observations)
        row['passed']=True
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
        row['rpc']=calls;row['clock_observations']=clock_observations;row['prompts']=prompts
        (project/'events.json').write_text(json.dumps(events,indent=2));row['events_sha256']=sha(project/'events.json')
        checks[name]=row;(ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
        print(json.dumps(dict(case=name,passed=row['passed'],error=row.get('error'))),flush=True)
    # Independent baselines retain both successful calls and counterexamples.
raise SystemExit(not all(row['passed'] for row in checks.values()))
