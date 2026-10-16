"""Retain native memory and TM/TC lookup behavior with immutable evidence."""
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
import native
import xml.etree.ElementTree as ET
from unittest.mock import patch
from installed_provenance import capture_application as capture
from manoeuvre_database_cases import CASES
from google.protobuf.message_factory import GetMessageClass
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
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
    (project/'data/mmd').mkdir(parents=True)
    runtime,tcp,api=create_servers(project/'dss.sqlite',0)
    if spec.get('faults'):
        old=runtime.engine.state()
        runtime.engine.reset('telemetry-'+name,faults=spec['faults'],expected_epoch=old['epoch'])
    for endpoint in (tcp,api):threading.Thread(target=endpoint.serve_forever,daemon=True).start()
    transport=Transport('http://127.0.0.1:'+str(api.server_port),tcp.server_address)
    journal=Journal(project/'driver.sqlite');dispatcher=Dispatcher(transport,journal)
    identity=dict(session=uuid.uuid4().hex,procedure=uuid.uuid4().hex,definition=name,
        version='manoeuvre-database-baseline',controller_epoch=1,procedure_fence=1,mode='Development',release=None)
    calls=[];events=[];controls=[]
    row=dict(passed=False,dimension=spec['dimension'],source=spec['source'],states=[],
        initial_ground=dispatcher.ground.state(),initial_dss=runtime.engine.state(),
        initial_packet_hex=runtime.engine.telemetry()['packet_hex'])
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
        # Configure a real DB-manager location before the native context reads it.
        # No procedure, helper, RPC response or installed source is patched.
        original_check_output=native.subprocess.check_output
        def configured_example(command,*args,**kwargs):
            result=original_check_output(command,*args,**kwargs)
            if command[:2]==['spell-native','init-example']:
                context=Path(command[2])/'config/contexts/context_example.xml'
                (project/'context-before.xml').write_bytes(context.read_bytes())
                tree=ET.parse(context)
                for item in list(tree.getroot().find('databases').findall("location[@name='mmd']")):
                    tree.getroot().find('databases').remove(item)
                ET.SubElement(tree.getroot().find('databases'),'location',name='mmd',type='file',ext='IMP').text=str(project/'data/mmd')
                tree.write(context,encoding='utf-8')
                (project/'context-configured.xml').write_bytes(context.read_bytes())
            return result
        with patch('native.subprocess.check_output',configured_example):session.start()
        session.pump=drain
        session.request('CMD_RUN',send=True);deadline=time.monotonic()+90
        feeding=False;last_token=None;next_tick=0
        while time.monotonic()<deadline:
            request_path=project/'fixture-request.json'
            if request_path.exists():
                command=json.loads(request_path.read_bytes())
                if command['token']!=last_token:
                    last_token=command['token']
                    before=runtime.engine.state()
                    before_packet=runtime.engine.telemetry()['packet_hex']
                    if command['action']=='reset':
                        runtime.engine.reset('telemetry-recovery-'+name,faults=command['faults'],expected_epoch=before['epoch'])
                        transport.close()
                        transport=Transport('http://127.0.0.1:'+str(api.server_port),tcp.server_address)
                        dispatcher.transport=transport
                        dispatcher.ground=type(dispatcher.ground)(transport,journal)
                    elif command['action']=='step':
                        runtime.engine.control('STEP',before['epoch'],before['revision'])
                    elif command['action']=='feed':feeding=command['enabled']
                    elif command['action']=='link':
                        shape=p.DESCRIPTOR.services_by_name['SPELLDriverInterface_RSC'].methods_by_name['SetLink'].input_type
                        body=GetMessageClass(shape)(name='TM',status=command['enabled'])
                        dispatch('/spell.driver.SPELLDriverInterface_RSC/SetLink',body.SerializeToString())
                    else:raise ValueError('Unknown telemetry fixture action')
                    after=runtime.engine.state()
                    after_packet=runtime.engine.telemetry()['packet_hex']
                    answer=dict(state=after,ground=dispatcher.ground.state(),packet_hex=after_packet)
                    controls.append(dict(command=command,before=before,after=after,before_packet_hex=before_packet,after_packet_hex=after_packet))
                    temporary=project/('fixture-'+last_token+'.tmp');temporary.write_text(json.dumps(answer))
                    temporary.replace(project/('fixture-'+last_token+'.json'))
            if feeding and time.monotonic()>=next_tick:
                current=runtime.engine.state()
                runtime.engine.control('STEP',current['epoch'],current['revision'])
                next_tick=time.monotonic()+.5
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
        row['final_packet_hex']=runtime.engine.telemetry()['packet_hex']
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
        row['rpc']=calls;row['fixture_controls']=controls
        (project/'events.json').write_text(json.dumps(events,indent=2));row['events_sha256']=sha(project/'events.json')
        checks[name]=row;(ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
        print(json.dumps(dict(case=name,passed=row['passed'],error=row.get('error'))),flush=True)
    # Independent baselines retain both successful calls and counterexamples.
raise SystemExit(not all(row['passed'] for row in checks.values()))
