"""Interrupt real waits over native IPC, retaining timers and binary TM evidence."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
import uuid

sys.path[:0] = ['/opt/host', '/workspace/fixture', '/workspace']
from native import NativeSession
from installed_provenance import capture
from wait_control_cases import CASES
from dss.local import create_servers
from openbexi_spell_dss.transport import Transport
from openbexi_spell_dss.journal import Journal
from openbexi_spell_dss.rpc import Dispatcher
from openbexi_spell_dss.server import Server

ROOT = Path('/workspace')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
(ROOT/'runtime.json').write_text(json.dumps(capture(), indent=2))
(ROOT/'host-inputs.json').write_text(json.dumps({p.name:sha(p) for p in Path('/opt/host').glob('*.py')}))
checks = {}
for name, spec in CASES.items():
    project = ROOT/name.replace(':', '-')
    project.mkdir()
    (project/'main.py').write_text(spec['source'])
    runtime, tcp, api = create_servers(project/'dss.sqlite', 0)
    for endpoint in (tcp, api):
        threading.Thread(target=endpoint.serve_forever, daemon=True).start()
    transport = Transport('http://127.0.0.1:'+str(api.server_port), tcp.server_address)
    journal = Journal(project/'driver.sqlite')
    dispatcher = Dispatcher(transport, journal)
    identity = dict(session=uuid.uuid4().hex, procedure=uuid.uuid4().hex,
        definition=name, version='wait-controls', controller_epoch=1, procedure_fence=1,
        mode='Development', release=None)
    events, calls, actions = [], [], []
    row = dict(passed=False, states=[], source=spec['source'], dimension=spec['dimension'])

    def tick():
        state = runtime.engine.state()
        runtime.engine.control('STEP', state['epoch'], state['revision'])
        return runtime.engine.state()['core']['tick']

    def dispatch(path, raw):
        call = dict(path=path, request=raw.hex(), started=time.monotonic())
        calls.append(call)
        try:
            result = dispatcher.dispatch(path, raw, identity, uuid.uuid4().hex, lambda:None)
            call['response'] = result.hex()
            return result
        except Exception as error:
            call['error'] = repr(error)
            raise
        finally:
            call['seconds'] = time.monotonic()-call['started']

    server = Server(dispatch)
    plan = {k:v for k,v in spec.items() if k!='source'}
    plan['expected_tick'] = tick()+1
    (project/'plan.json').write_text(json.dumps(plan))
    session = NativeSession(project, project/'main.py', {}, driver_port=server.port)

    def drain():
        while True:
            try: event = session.events.get_nowait()
            except queue.Empty: return
            event['received_monotonic'] = time.monotonic()
            events.append(event)
            assert event.get('event')!='connectionError', event
            assert event.get('message',{}).get('id')!='MSG_PROMPT', event

    def status():
        drain()
        value = session.request('REQ_EXEC_STATUS')['ExecutorStatus']
        row['states'].append(dict(status=value, monotonic=time.monotonic(), epoch=time.time()))
        return value

    def wait(expected, seconds=6):
        deadline = time.monotonic()+seconds
        while time.monotonic()<deadline:
            current = status()
            if current==expected: return
            assert current not in ('ERROR','ABORTED','FINISHED'), (expected,current)
            time.sleep(.02)
        raise TimeoutError('Expected '+expected+', saw '+str(row['states'][-5:]))

    def command(value):
        actions.append(dict(command=value, monotonic=time.monotonic(), epoch=time.time()))
        session.request(value, send=True)

    def tm_calls():
        return [x for x in calls if x['path'].endswith('/RefreshItem')]

    try:
        session.start()
        session.pump = drain
        assert status()=='PAUSED'
        command('CMD_RUN')
        wait('WAITING')
        if spec['kind']=='telemetry':
            until=time.monotonic()+3
            while len(tm_calls())<2 and time.monotonic()<until:
                assert status()=='WAITING'
                time.sleep(.02)
            assert len(tm_calls())>=2
        ready=json.loads((project/'ready.json').read_bytes())
        row['ready']=ready
        assert len(ready['rejected'])==(1 if spec['dimension']=='failure' else 0)
        command('CMD_INTERRUPT')
        wait('INTERRUPTED')
        # A status reply is a native round trip behind the interrupt command.
        # Give an already-running callback one bounded drain before fixing the baseline.
        settle=time.monotonic()+.3
        while time.monotonic()<settle:
            assert status()=='INTERRUPTED'
            time.sleep(.02)
        if spec['dimension']=='failure':
            command('CMD_INTERRUPT')
            assert status()=='INTERRUPTED'
        frozen_calls=len(tm_calls())
        frozen_countdown=len([x for x in events if x.get('message',{}).get('fields',{}).get('ItemName')=='COUNTDOWN'])
        frozen_at=time.monotonic()
        held_until=time.monotonic()+.55
        if spec['kind']!='telemetry' and spec['dimension']=='boundary':
            held_until=max(held_until,time.monotonic()+ready['target']-time.time()+.45)
        if spec['kind']=='telemetry' and (spec['dimension']=='boundary' or spec['action']=='skip'):
            row['condition_satisfied_at']=time.monotonic()
            assert tick()==plan['expected_tick']
        while time.monotonic()<held_until:
            assert status()=='INTERRUPTED'
            assert not (project/'returned.json').exists()
            assert len(tm_calls())==frozen_calls, 'Telemetry continued while interrupted'
            count=len([x for x in events if x.get('message',{}).get('fields',{}).get('ItemName')=='COUNTDOWN'])
            assert count==frozen_countdown, 'Countdown continued while interrupted'
            time.sleep(.025)
        row['held']=dict(acquisitions=frozen_calls,countdowns=frozen_countdown,since=frozen_at,until=time.monotonic())
        command('CMD_STEP' if spec['action']=='step' else 'CMD_SKIP')
        if spec['kind']=='telemetry' and spec['action']=='step' and spec['dimension']!='boundary':
            wait('WAITING')
            row['condition_satisfied_at']=time.monotonic()
            assert tick()==plan['expected_tick']
        wait('PAUSED')
        paused_at=time.time()
        row['paused_at']=paused_at
        if spec['kind']!='telemetry' and spec['action']=='step':
            assert paused_at>=ready['target'], (paused_at,ready['target'])
            assert paused_at<=max(ready['target'],actions[-1]['epoch'])+1, 'Original target shifted'
        if spec['action']=='skip':
            assert paused_at<actions[-1]['epoch']+1, 'Skip did not cancel promptly'
        for _ in range(3):
            assert status()=='PAUSED'
            assert not (project/'returned.json').exists(), 'Statement after wait executed without resumption'
        command('CMD_RUN')
        wait('FINISHED')
        row['returned']=json.loads((project/'returned.json').read_bytes())
        row['recovery']=json.loads((project/'finished.json').read_bytes())
        assert row['returned']['value'] is (spec['action']=='step')
        assert .35<=row['recovery']['recovery_elapsed']<2
        if spec['kind']=='telemetry' and spec['action']=='step':
            assert len(tm_calls())>frozen_calls
            from spell.stubs.SPELLDriver_pb2 import TmItemValue
            from spell.utils.grpc_utils import UnpackValue
            row['last_tm_value']=UnpackValue(TmItemValue.FromString(bytes.fromhex(tm_calls()[-1]['response'])).engValue)
            assert row['last_tm_value']==plan['expected_tick']
        if spec['kind']=='telemetry' and spec['action']=='skip':
            assert len(tm_calls())==frozen_calls
        row['passed']=True
    except Exception:
        row['error']=traceback.format_exc()
    finally:
        if session.log:
            session.log.flush(); session.log.seek(0)
            log=session.log.read()
            (project/'native.log').write_text(log)
            row['native_log_sha256']=sha(project/'native.log')
            if 'AddressSanitizer:' in log or 'runtime error:' in log:
                row.update(passed=False,sanitizer_error=True)
        try: session.close()
        except Exception: row.update(passed=False,cleanup_error=traceback.format_exc())
        server.close()
        for endpoint in (tcp,api): endpoint.shutdown(); endpoint.server_close()
        transport.close(); journal.close(); runtime.engine.close()
        row.update(actions=actions,rpc=calls)
        (project/'events.json').write_text(json.dumps(events,indent=2))
        row['events_sha256']=sha(project/'events.json')
        checks[name]=row
        (ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
        print(json.dumps(dict(case=name,passed=row['passed'],error=row.get('error'))),flush=True)
    if not row['passed']:
        break  # Preserve the first failure before spending time on dependent cases.
raise SystemExit(not all(x['passed'] for x in checks.values()))
