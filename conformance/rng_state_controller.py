"""Native rng contracts against the real persistent GENERIC ground service."""
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
sys.path.insert(0, '/workspace')
from rng_state_provenance import capture
from native import NativeSession
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
                definition='RNG_STATE/main.py', version='native-rng-state-contracts',
                controller_epoch=1, procedure_fence=1, mode='Development', release=None)


def dispatch(path, raw):
    current = project / 'current.json'
    record = dict(path=path, request=raw.hex(), started=time.monotonic(),
                  check=json.loads(current.read_text())['check'] if current.exists() else None)
    request_id=uuid.uuid4().hex
    record['request_id']=request_id
    calls.append(record)
    try:
        result = dispatcher.dispatch(path, raw, identity, request_id, lambda: None)
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
                elif command['action'] not in ('observe', 'rng_state','reopen','legacy_reopen','arm_receipt_failure'):
                    raise ValueError('Unknown fixture control')
                migration_error=None
                if command['action']=='arm_receipt_failure':
                    original_finish=journal.finish
                    def lose_receipt(identity,request_id,receipt):
                        journal.finish=original_finish
                        raise ConnectionError('Controlled receipt loss after actual Ground transition')
                    journal.finish=lose_receipt
                if command['action']=='legacy_reopen':
                    with journal.transaction():
                        journal.db.execute('UPDATE ground SET state=? WHERE namespace=?',(command['encoded'],dispatcher.ground.namespace))
                        journal.db.execute('INSERT OR IGNORE INTO ground VALUES(?,?)',('rng-unused',' { "retain" : [0, false, 42] } '))
                if command['action'] in ('reopen','legacy_reopen'):
                    journal.close()
                    journal=Journal('/workspace/driver.sqlite')
                    try:
                        dispatcher=Dispatcher(transport,journal)
                    except Exception as error:
                        migration_error=type(error).__name__+': '+str(error)
                state = runtime.engine.state()
                answer = {'state': state, 'migration_error':migration_error}
                if command['action'] in ('rng_state','reopen','legacy_reopen'):
                    with journal.lock:
                        row = journal.db.execute('SELECT state FROM ground WHERE namespace=?', (dispatcher.ground.namespace,)).fetchone()
                        answer['ground'] = json.loads(row[0])
                        answer['ground_encoded']=row[0]
                        answer['other_namespaces']={r[0]:r[1] for r in journal.db.execute('SELECT namespace,state FROM ground WHERE namespace!=?',(dispatcher.ground.namespace,))}
                        answer['effects'] = [dict(request_id=r[0], state=r[1], receipt=r[2].hex() if r[2] is not None else None, digest=r[3]) for r in journal.db.execute('SELECT request_id,state,receipt,digest FROM effects ORDER BY created_ns')]
                    answer['rpc'] = list(calls)
                if command['action'] == 'observe':
                    answer['rpc'] = list(calls)
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
            choices = [ACTION_NAMES.get(code, code) for code in codes]
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
        raise TimeoutError('Native rng procedure did not finish')
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
            result.update(passed=False, thread_error='Unhandled original runtime thread exception')
    try:
        session.close()
    except Exception as error:
        result.update(passed=False, cleanup_error=str(error))
    server.close()
    for endpoint in (tcp, api):
        endpoint.shutdown()
        endpoint.server_close()
    result.update(events=events, rpc=calls, controls=controls, prompts=prompts, state=runtime.engine.state())
    runtime.engine.close()
    Path('/workspace/observations.json').write_text(json.dumps(result, indent=2) + '\n')
    Path('/workspace/runtime.json').write_text(json.dumps(capture(), indent=2)+'\n')
    print(json.dumps({key:value for key,value in result.items() if key not in ('events','rpc','state')}),flush=True)
