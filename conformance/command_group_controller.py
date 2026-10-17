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
from command_group_provenance import capture
if os.environ.get('OPENBEXI_CONFORMANCE_COMPOSED') == '1':
    from installed_provenance import capture_application as capture
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
from command_group_cases import CASES
from clock_step import try_step
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
        version='command-group-candidate',controller_epoch=1,procedure_fence=1,mode='Development',release=None)
    calls=[];events=[];clock_observations=[];clock_conflicts=[];last_tick=0;competitor=None
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
        session.request('CMD_RUN',send=True);deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            drain();status=session.request('REQ_EXEC_STATUS')['ExecutorStatus']
            pending=[call for call in calls if call['path'].endswith(('_TC/SendCommand','_TC/SendList','_TC/SendBlock')) and 'elapsed' not in call]
            if pending and spec.get('clock') and time.monotonic()-last_tick>=.1:
                state=runtime.engine.state()
                operations=runtime.engine.evidence(state['scenario_id'])['operations']
                acks=[r for r in operations if r['acknowledgement']['stage']=='ACKNOWLEDGEMENT']
                if spec.get('competitor') and competitor is None and (
                        spec['clock']=='onboard' and len(acks)==2 or spec['clock']=='ground' and len(operations)>=5):
                    other=dict(identity,procedure=uuid.uuid4().hex,definition='independent-competing-controller')
                    accepted,receipts=transport.command('CMD2',[],other,'competing-uplink',lambda:None)
                    assert accepted is False and len(receipts)==1
                    assert receipts[0]['outcome']=='REJECTED' and receipts[0]['detail']['reason']=='UPLINK_GROUP_BUSY'
                    competitor=dict(accepted=accepted,receipts=receipts,before=state,after=runtime.engine.state())
                    assert competitor['before']['core']==competitor['after']['core']
                    operations=runtime.engine.evidence(state['scenario_id'])['operations']
                ready=spec['clock']!='onboard' or len(acks)==len(spec['expected_members'])
                if ready:
                    if try_step(runtime.engine,state,pending[-1]['request'],
                                [r['acknowledgement']['stage'] for r in operations],
                                clock_observations,clock_conflicts):
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
        assert state['core']['loaded_commands_count']==spec['expected_loaded']
        from dss.packets import decode_tc
        frames=[decode_tc(bytes.fromhex(r['packet_hex'])) for r in operations if r['acknowledgement']['stage']=='TRANSPORT' and r['acknowledgement']['outcome']=='ACCEPTED']
        names=[e['command_name'] for frame in frames for e in frame.get('elements',[frame])]
        assert names==spec['expected_members'],names
        if name.startswith('Block') and spec['expected_loaded']:
            assert len(frames)==1 and 'elements' in frames[0]
        if 'LoadOnly' in name:
            assert all(r['acknowledgement']['stage'] in ('TRANSPORT','LOADING') for r in operations)
            runtime.engine.control('STEP',state['epoch'],state['revision'],10)
            assert runtime.engine.state()['core']['commands_executed']==0
        if spec.get('clock')=='onboard':
            assert any(r['before']['core']['commands_executed']==0 and r['stages'].count('ACKNOWLEDGEMENT')==2 for r in clock_observations)
        if spec.get('competitor'):assert competitor is not None
        if spec.get('clock')=='ground':
            assert any(r['stages']==[] for r in clock_observations)
            uplinks=[r['acknowledgement'] for r in operations if r['acknowledgement']['stage']=='TRANSPORT' and r['acknowledgement']['outcome']=='ACCEPTED']
            assert uplinks[0]['simulation_time_ns']>=150000000
            assert uplinks[1]['simulation_time_ns']-uplinks[0]['simulation_time_ns']>=150000000
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
        transport.close()
        row['rpc']=calls;row['clock_observations']=clock_observations;row['clock_conflicts']=clock_conflicts
        row['competitor']=competitor
        row['uplink_groups']=list(runtime.uplink_groups.history)
        if journal.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='command_results'").fetchone():
            row['member_results']=[json.loads(r[0]) for r in journal.db.execute('SELECT result FROM command_results ORDER BY rowid')]
        else:row['member_results']=[]
        (project/'events.json').write_text(json.dumps(events,indent=2));row['events_sha256']=sha(project/'events.json')
        journal.close();runtime.engine.close()
        checks[name]=row;(ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
        print(json.dumps(dict(case=name,passed=row['passed'],error=row.get('error'))),flush=True)
    # Independent baselines retain both successful calls and counterexamples.
raise SystemExit(not all(row['passed'] for row in checks.values()))
