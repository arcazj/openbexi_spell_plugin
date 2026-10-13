"""Exercise original native ARGS/IVARS dictionary IPC while an executor is paused."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0, '/opt/host')
from native import NativeSession

project = Path('/workspace')
events = []
results = {'checks': {}, 'observations': []}
source = '''from pathlib import Path
from spell.runtime import ARGS, IVARS
from spell.lib.adapter.data import DataContainer, Var
from spell.lang.constants import LONG, STRING
from spell.lang.functions import Pause
assert isinstance(ARGS, DataContainer) and isinstance(IVARS, DataContainer)
assert len(ARGS) == 0 and len(IVARS) == 0
Path('container-types.json').write_text(__import__('json').dumps({
    'ARGS': str(type(ARGS)), 'IVARS': str(type(IVARS))}))
for container in (ARGS, IVARS):
    container['count'] = Var(Default=3, Type=LONG, Range=[0,10])
    container['text'] = Var(Default='initial', Type=STRING)
Path('ready.txt').write_text('ready')
Pause()
for container in (ARGS, IVARS):
    assert container['count'] == 7
    assert container['text'] == 'café λ'
    container['count'] = 8
    assert container['count'] == 8
Path('complete.txt').write_text('complete')
'''
(project/'main.py').write_text(source, encoding='utf-8')
session = NativeSession(project, project/'main.py', {})


def drain():
    while True:
        try:
            event = session.events.get_nowait()
        except queue.Empty:
            break
        events.append(event)
        if event.get('event') == 'connectionError':
            raise RuntimeError(event)


def request(identifier, fields):
    result = session.request(identifier, fields)
    results['observations'].append(dict(id=identifier, fields=fields, result=result))
    return result


def observe(identifier, dimension, condition, actual, oracle):
    results['checks'][identifier + ':' + dimension] = dict(
        contracts=[], dimension=dimension, passed=bool(condition), actual=actual,
        oracle=oracle, evidence_kind='diagnostic-native-client-editing')


try:
    session.start()
    session.pump = drain
    session.request('CMD_RUN', send=True)
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        drain()
        status = session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
        if status == 'PAUSED' and (project/'ready.txt').exists():
            break
        assert status not in ('ERROR', 'ABORTED', 'FINISHED'), status
        time.sleep(.02)
    else:
        raise TimeoutError('Did not pause for client editing')
    for dictionary in ('ARGS', 'IVARS'):
        response = request('REQ_GET_DICTIONARY', {'DictName': dictionary})
        original = 'count\x053\x05\x05LONG\x05[0,10]\x05[]\x05false\x04text\x05initial\x05\x05STRING\x05[]\x05[]\x05false'
        observe(dictionary, 'positive', response.get('DictContents') == original, response,
                'LRM p.86 original typed ARGS/IVARS are visible to the client with each variable value/type/range/format/confirmation field')
        invalid = request('REQ_UPD_DICTIONARY', {'DictName': dictionary,
            'DictContents': '\x05'.join(['count', repr('bad'), 'NONE', 'False'])})
        observe(dictionary, 'failure', bool(invalid.get('Error')), invalid,
                'Native client assignment of STRING to a declared LONG must return an explicit error without a user prompt')
        for name, value in [('count', '7'), ('text', repr('café λ'))]:
            response = request('REQ_UPD_DICTIONARY', {'DictName': dictionary,
                'DictContents': '\x05'.join([name, value, 'NONE', 'False'])})
            assert not response.get('Error'), response
        response = request('REQ_GET_DICTIONARY', {'DictName': dictionary})
        updated = 'count\x057\x05\x05LONG\x05[0,10]\x05[]\x05false\x04text\x05café λ\x05\x05STRING\x05[]\x05[]\x05false'
        observe(dictionary, 'boundary', response.get('DictContents') == updated, response,
                'Actual client editing preserves Unicode text and native typed field metadata')
        observe(dictionary, 'recovery', response.get('DictContents') == updated, response,
                'An invalid assignment followed by valid edits leaves both original native containers usable and exposes the new values')
    session.request('CMD_RUN', send=True)
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        drain()
        status = session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
        if status in ('FINISHED', 'ERROR', 'ABORTED'):
            results['resumed_status'] = status
            break
        time.sleep(.02)
    else:
        raise TimeoutError('Native executor did not finish after editing')
    results['continued_after_edits'] = (project/'complete.txt').exists()
    results['passed'] = (status == 'FINISHED' and results['continued_after_edits']
                         and all(row['passed'] for row in results['checks'].values()))
finally:
    if session.log:
        session.log.flush()
        session.log.seek(0)
        (project/'native.log').write_text(session.log.read(), encoding='utf-8')
    session.close()
    results['runtime_host_sha256'] = hashlib.sha256(Path('/opt/host/native.py').read_bytes()).hexdigest()
    (project/'dta-edit-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    (project/'dta-edit-wire.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
