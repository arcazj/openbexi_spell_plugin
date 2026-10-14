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
from send_verify_provenance import capture
provenance = capture()
integrated = provenance['integrated']
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
                definition='SEND_VERIFY/main.py', version='native-command-contracts',
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
    armed_tick = None
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
                elif command['action'] == 'tick_after_refresh':
                    assert armed_tick is None
                    armed_tick = dict(check=current_check, after=len(calls), delay=command['delay'])
                elif command['action'] != 'observe':
                    raise ValueError('Unknown fixture control')
                state = runtime.engine.state()
                answer = {'state': state}
                if command['action'] == 'observe':
                    answer['rpc'] = list(calls)
                    answer['evidence'] = runtime.engine.evidence(state['scenario_id'])
                    answer['controls'] = list(controls)
                controls.append(dict(command=command, state=state))
                temporary = project / ('fixture-' + last_token + '.tmp')
                temporary.write_text(json.dumps(answer))
                temporary.replace(project / ('fixture-' + last_token + '.json'))
        if armed_tick is not None:
            refreshes = [row for row in calls[armed_tick['after']:]
                         if row['check'] == armed_tick['check'] and row['path'].endswith('/RefreshItem')]
            if refreshes and time.monotonic() >= refreshes[0]['started'] + armed_tick['delay']:
                assert 'response' not in refreshes[0], 'Fresh read completed before the only new sample'
                state = runtime.engine.state()
                tick_started = time.monotonic()
                runtime.engine.control('STEP', state['epoch'], state['revision'])
                controls.append(dict(action='scheduled_tick', check=armed_tick['check'],
                                     monotonic=tick_started, state=runtime.engine.state()))
                armed_tick = None
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
        'diagnostic_overlay': provenance,
        'interpreter': sys.version,
        'manifests': manifests,
        'installed': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
    }, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in ('events', 'rpc', 'state')}), flush=True)
