"""Own real loopback DSS, original-schema gRPC and original native executor."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
import uuid

sys.path.insert(0, '/workspace/fixture')
sys.path.insert(0, '/opt/host')
from native import NativeSession
sys.path.insert(0, '/workspace')
from installed_provenance import capture
if Path('/opt/event-text-patch').exists():
    from event_text_provenance import capture
integrated = capture()
from dss.local import create_servers
from openbexi_spell_dss.transport import Transport
from openbexi_spell_dss.journal import Journal
from openbexi_spell_dss.rpc import Dispatcher
from openbexi_spell_dss.server import Server

project = Path('/workspace/procedure')
events, calls, controls, prompts, pending = [], [], [], [], []
ACTION_NAMES = dict(A='ABORT', R='REPEAT', S='RESEND', C='RECHECK', K='SKIP', N='NOACTION', Q='CANCEL', H='HANDLE')
runtime, tcp, api = create_servers('/workspace/dss.sqlite', 0)
for endpoint in (tcp, api):
    threading.Thread(target=endpoint.serve_forever, daemon=True).start()
transport = Transport('http://127.0.0.1:' + str(api.server_port), tcp.server_address)
journal = Journal('/workspace/driver.sqlite')
dispatcher = Dispatcher(transport, journal)
identity = dict(session=uuid.uuid4().hex, procedure=uuid.uuid4().hex,
                definition='EVENTS/main.py', version='native-event-resend-contracts',
                controller_epoch=1, procedure_fence=1, mode='Development', release=None)


def dispatch(path, raw):
    current = project / 'current.json'
    record = dict(path=path, request=raw.hex(), started=time.monotonic(),
                  check=json.loads(current.read_text())['check'] if current.exists() else None)
    calls.append(record)
    try:
        result = dispatcher.dispatch(path, raw, identity, uuid.uuid4().hex, lambda: None)
        record['response'] = result.hex()
        return result
    except Exception as error:
        record['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        record['seconds'] = time.monotonic() - record['started']


server = Server(dispatch)
session = NativeSession(project, project / 'main.py', {}, driver_port=server.port)
result = {'passed': False}


def drain():
    while True:
        try:
            event = session.events.get_nowait()
        except queue.Empty:
            return
        events.append(event)
        if event.get('event') == 'connectionError':
            raise RuntimeError(event)
        message = event.get('message', {})
        if message.get('id') == 'MSG_PROMPT':
            pending.append(message)


try:
    session.start()
    session.pump = drain
    session.request('CMD_RUN', send=True)
    deadline, next_tick = time.monotonic() + 600, 0
    feeding, last_token = True, None
    current_check, current_started = None, time.monotonic()
    while time.monotonic() < deadline:
        current_path = project / 'current.json'
        if current_path.exists():
            observed_check = json.loads(current_path.read_text())['check']
            if observed_check != current_check:
                current_check, current_started = observed_check, time.monotonic()
            elif time.monotonic() - current_started > 25:
                raise TimeoutError('Native check stalled: ' + current_check)
        command_path = project / 'fixture-request.json'
        if command_path.exists():
            command = json.loads(command_path.read_text())
            if command['token'] != last_token:
                last_token = command['token']
                if command['action'] == 'feed':
                    feeding = command['value']
                elif command['action'] == 'tick':
                    state = runtime.engine.state()
                    runtime.engine.control('STEP', state['epoch'], state['revision'], command.get('ticks', 1))
                elif command['action'] != 'observe':
                    raise ValueError('Unknown fixture control')
                state = runtime.engine.state()
                answer = {'state': state}
                if command['action'] == 'observe':
                    answer['rpc'] = list(calls)
                    answer['native'] = list(events)
                    answer['repairs'] = [row for row in controls if 'repair_mode' in row]
                    answer['event_journal'] = [dict(message=row[0],severity=row[1],scope=row[2]) for row in journal.db.execute('SELECT message,severity,scope FROM events ORDER BY created_ns')]
                    answer['evidence'] = runtime.engine.evidence(state['scenario_id'])
                controls.append(dict(command=command, state=state))
                temporary = project / ('fixture-' + last_token + '.tmp')
                temporary.write_text(json.dumps(answer))
                temporary.replace(project / ('fixture-' + last_token + '.json'))
        if feeding and time.monotonic() >= next_tick:
            state = runtime.engine.state()
            runtime.engine.control('STEP', state['epoch'], state['revision'])
            next_tick = time.monotonic() + .5
        drain()
        while pending:
            fields = pending.pop(0)['fields']
            identifier = json.loads((project / 'current.json').read_text())['check']
            plans = json.loads((project / 'prompt-plans.json').read_text())
            index = len([row for row in prompts if row['check'] == identifier])
            assert index < len(plans), ('Unexpected native prompt', identifier, fields)
            plan = plans[index]
            codes = fields.get('ExpectedValues', '').split('\x04')
            choices = codes if plan.get('raw_codes') else [ACTION_NAMES.get(code, code) for code in codes]
            for fragment in plan.get('contains', []):
                assert fragment in str(fields), (fragment, fields)
            assert len(choices) == len(plan['choices']) and set(choices) == set(plan['choices']), (plan, fields)
            assert plan['answer'] in choices
            if plan.get('repair_mode'):
                from openbexi_spell_dss.codec import pack
                from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
                repair_identity = dict(identity,procedure=uuid.uuid4().hex,
                                       definition='fixture/mode-repair')
                command = p.CommandDesc(command=p.TcItemDesc(mnemonic='TC.SIMULATOR.SET_MODE'),
                    args=pack([['MODE',plan['repair_mode']]]),config=pack({'Timeout':5}))
                path = '/spell.driver.SPELLDriverInterface_TC/SendCommand'
                began = time.monotonic()
                response = dispatcher.dispatch(path,command.SerializeToString(),repair_identity,uuid.uuid4().hex,lambda:None)
                controls.append(dict(repair_mode=plan['repair_mode'],identity=repair_identity,
                    path=path,request=command.SerializeToString().hex(),response=response.hex(),seconds=time.monotonic()-began))
                assert response == b'\x08\x01', response
            answer = str(choices.index(plan['answer']))
            prompts.append(dict(check=identifier, fields=fields, choices=choices, answer=plan['answer']))
            session.request('MSG_ANSWER', {'ReturnValue': answer}, send=True)
        result['status'] = session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
        if result['status'] in ('FINISHED', 'ERROR', 'ABORTED'):
            break
        time.sleep(.01)
    else:
        raise TimeoutError('Native command procedure did not finish')
    drain()
    result['passed'] = result['status'] == 'FINISHED'
except BaseException as error:
    result.update(error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc())
finally:
    if session.log:
        session.log.flush()
        session.log.seek(0)
        diagnostic = session.log.read()
        Path('/workspace/native.log').write_text(diagnostic)
        if 'Exception in thread' in diagnostic:
            result.update(passed=False, thread_error='Unhandled original verifier thread exception')
    try:
        session.close()
    except Exception as error:
        result.update(passed=False, cleanup_error=str(error))
    server.close()
    for endpoint in (tcp, api):
        endpoint.shutdown()
        endpoint.server_close()
    result.update(events=events, rpc=calls, controls=controls, prompts=prompts, state=runtime.engine.state(),
                  evidence=runtime.engine.evidence(runtime.engine.state()['scenario_id']))
    transport.close()
    journal.close()
    runtime.engine.close()
    Path('/workspace/observations.json').write_text(json.dumps(result, indent=2) + '\n')
    paths = [Path('/opt/host/native.py')]
    for package in ('spell', 'spell_native', 'openbexi_dss_proxy', 'openbexi_spell_dss'):
        paths += list(Path('/usr/local/lib/python3.13/site-packages', package).rglob('*.py'))
        paths += list(Path('/usr/local/lib/python3.13/site-packages', package).rglob('*.so'))
    paths += [path for path in Path('/usr/local/lib/python3.13/site-packages/spell_native/bin').iterdir() if path.is_file()]
    paths += [path for path in (Path('/opt/dta-native-patch/manifest.json'),
              Path('/opt/obs-conformance-patch/manifest.json'),
              Path('/opt/obs-conformance-patch/obs_patches.py'),
              Path('/opt/obs-conformance-patch/obs_combined.Dockerfile')) if path.exists()]
    manifests = {}
    for name in ('dta-native-patch', 'obs-conformance-patch', 'cmd-conformance-patch'):
        manifest = Path('/opt', name, 'manifest.json')
        if manifest.exists():
            manifests[name] = json.loads(manifest.read_text())
    if 'dta-native-patch' in manifests:
        for name, expected in manifests['dta-native-patch']['artifacts'].items():
            path = Path('/usr/local/lib/python3.13/site-packages/spell_native/bin', name)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
    if 'obs-conformance-patch' in manifests:
        for name, description in manifests['obs-conformance-patch'].items():
            path = Path('/usr/local/lib/python3.13/site-packages', name)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == description['sha256'], name
    if 'cmd-conformance-patch' in manifests:
        for name, description in manifests['cmd-conformance-patch'].items():
            path = Path('/usr/local/lib/python3.13/site-packages',name)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == description['sha256'], name
    paths += [p for p in Path('/opt/cmd-conformance-patch').rglob('*') if p.is_file()]
    Path('/workspace/runtime.json').write_text(json.dumps({
        'integrated': integrated,
        'interpreter': sys.version,
        'manifests': manifests,
        'installed': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
    }, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in ('events', 'rpc', 'state')}), flush=True)
