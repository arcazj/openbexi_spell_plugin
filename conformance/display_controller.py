"""Observe native SPELL display helpers through original RPC and a real local viewer."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
from urllib.request import urlopen
import uuid

sys.path[:0] = ['/opt/host', '/workspace/fixture', '/workspace']
from native import NativeSession
from display_provenance import capture
from dss.local import create_servers
from openbexi_spell_dss.transport import Transport
from openbexi_spell_dss.journal import Journal
from openbexi_spell_dss.rpc import Dispatcher
from openbexi_spell_dss.server import Server
from openbexi_spell_dss.display_viewer import create_server

ROOT = Path('/workspace')
project = ROOT / 'procedure'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(ROOT / 'runtime.json').write_text(json.dumps(capture(), indent=2))
(ROOT / 'host-inputs.json').write_text(json.dumps({p.name: sha(p) for p in Path('/opt/host').glob('*.py')}))
runtime, tcp, api = create_servers(ROOT / 'dss.sqlite', 0)
for endpoint in (tcp, api):
    threading.Thread(target=endpoint.serve_forever, daemon=True).start()
transport = Transport('http://127.0.0.1:' + str(api.server_port), tcp.server_address)
journal = Journal(ROOT / 'driver.sqlite')
dispatcher = Dispatcher(transport, journal)
identity = dict(session=uuid.uuid4().hex, procedure=uuid.uuid4().hex, definition='native-display',
                version='display-candidate', controller_epoch=1, procedure_fence=1, mode='Development', release=None)
calls, events, observations = [], [], []


def current():
    path = project / 'current.json'
    return json.loads(path.read_bytes())['check'] if path.exists() else None


def dispatch(path, raw):
    request_id = uuid.uuid4().hex
    row = dict(path=path, request=raw.hex(), request_id=request_id, check=current(), started=time.monotonic())
    calls.append(row)
    try:
        result = dispatcher.dispatch(path, raw, identity, request_id, lambda: None)
        row['response'] = result.hex()
        return result
    except Exception as error:
        row['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        row['elapsed'] = time.monotonic() - row['started']


def observe():
    with journal.lock:
        effects = [dict(request_id=row[0], state=row[1], receipt=row[2].hex() if row[2] is not None else None,
                        digest=row[3]) for row in journal.db.execute(
            'SELECT request_id,state,receipt,digest FROM effects ORDER BY created_ns')]
    return dict(ground=dispatcher.ground.state(), effects=effects,
                rpc=[row for row in calls if row['check'] == current()])


rpc = Server(dispatch)
viewer = create_server(lambda: dispatcher.ground.state())
viewer_thread = threading.Thread(target=viewer.serve_forever, daemon=True)
viewer_thread.start()
viewer_url = 'http://127.0.0.1:' + str(viewer.server_port)
session = NativeSession(project, project / 'main.py', {}, driver_port=rpc.port)
result = dict(passed=False)


def drain():
    while True:
        try:
            event = session.events.get_nowait()
        except queue.Empty:
            return
        events.append(event)
        assert event.get('event') != 'connectionError', event
        assert event.get('message', {}).get('id') != 'MSG_PROMPT', ('Unexpected native prompt', event)


try:
    session.start()
    session.pump = drain
    session.request('CMD_RUN', send=True)
    deadline = time.monotonic() + 1200
    last_token, last_check, check_started = None, None, time.monotonic()
    while time.monotonic() < deadline:
        check = current()
        if check != last_check:
            if last_check:
                path = project / 'checks.json'
                checks = json.loads(path.read_bytes()) if path.exists() else {}
                print(json.dumps(dict(case=last_check, passed=checks.get(last_check, {}).get('passed'))), flush=True)
            last_check, check_started = check, time.monotonic()
        if time.monotonic() - check_started > 240:
            raise TimeoutError('Display case stalled: ' + str(check))
        command_path = project / 'fixture-request.json'
        if command_path.exists():
            command = json.loads(command_path.read_bytes())
            if command['token'] != last_token:
                last_token = command['token']
                action = command['action']
                if action == 'reset':
                    def reset(state):
                        state.update(displays={}, display_applications={}, display_jobs={},
                                     display_application_sequence=0, display_job_sequence=0)
                        state['reports'] = {key: value for key,value in state['reports'].items()
                                            if not key.startswith('display-')}
                    dispatcher.ground.update(reset)
                    answer = observe()
                elif action == 'observe':
                    answer = observe()
                elif action == 'reopen':
                    journal.close()
                    journal = Journal(ROOT / 'driver.sqlite')
                    dispatcher = Dispatcher(transport, journal)
                    answer = observe()
                elif action in ('viewer', 'download'):
                    suffix = '' if action == 'viewer' else '/jobs/' + command['identity']
                    with urlopen(viewer_url + suffix, timeout=5) as response:
                        content, kind = response.read(), response.headers['Content-Type']
                    target = ROOT / 'downloads' / (check.replace(':', '-') + '-' + last_token +
                        ('.html' if action == 'viewer' else '.ps' if kind == 'application/postscript' else '.txt'))
                    target.parent.mkdir(exist_ok=True)
                    target.write_bytes(content)
                    answer = dict(media_type=kind, sha256=sha(target), artifact=target.relative_to(ROOT).as_posix())
                    answer['html' if action == 'viewer' else 'content'] = content.decode('utf-8')
                else:
                    raise ValueError('Unknown display fixture control')
                observations.append(dict(check=check, command=command, response=answer))
                temporary = project / ('fixture-' + last_token + '.tmp')
                temporary.write_text(json.dumps(answer), encoding='utf-8')
                temporary.replace(project / ('fixture-' + last_token + '.json'))
        drain()
        status = session.request('REQ_EXEC_STATUS')['ExecutorStatus']
        result['status'] = status
        if status in ('FINISHED', 'ERROR', 'ABORTED'):
            break
        time.sleep(.01)
    else:
        raise TimeoutError('Native display suite exceeded deadline')
    drain()
    checks = json.loads((project / 'checks.json').read_bytes())
    assert set(checks) == set(json.loads((project / 'cases.json').read_bytes()))
    assert all(row['passed'] for row in checks.values()), {key: row.get('error') for key,row in checks.items() if not row['passed']}
    assert status == 'FINISHED', status
    assert not any(row['state'] != 'RECEIPTED' for row in observe()['effects'])
    result['passed'] = True
except Exception:
    result['error'] = traceback.format_exc()
finally:
    if session.log:
        session.log.flush()
        session.log.seek(0)
        log = session.log.read()
        (ROOT / 'native.log').write_text(log)
        result['native_log_sha256'] = sha(ROOT / 'native.log')
        if 'AddressSanitizer:' in log or 'runtime error:' in log:
            result.update(passed=False, sanitizer_error=True)
    try:
        session.close()
    except Exception:
        result.update(passed=False, cleanup_error=traceback.format_exc())
    rpc.close()
    viewer.shutdown()
    viewer.server_close()
    viewer_thread.join(5)
    for endpoint in (tcp, api):
        endpoint.shutdown()
        endpoint.server_close()
    transport.close()
    journal.close()
    runtime.engine.close()
    for name, value in (('rpc.json', calls), ('events.json', events), ('observations.json', observations)):
        (ROOT / name).write_text(json.dumps(value, indent=2), encoding='utf-8')
        result[name.removesuffix('.json') + '_sha256'] = sha(ROOT / name)
    (ROOT / 'controller-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
raise SystemExit(not result['passed'])
