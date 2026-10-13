"""Exercise original native ARGS/IVARS dictionary IPC while an executor is paused."""
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0, '/opt/host')
from native import NativeSession
sys.path.insert(0, '/workspace')
from installed_provenance import capture

project = Path('/workspace')
events = []
results = {'checks': {}, 'observations': []}
runtime = {'host_sha256': hashlib.sha256(Path('/opt/host/native.py').read_bytes()).hexdigest()}
integrated = capture()
if integrated is not None:
    runtime['integrated'] = integrated
manifest_path = Path('/opt/dta-native-patch/manifest.json')
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_bytes())
    distribution = importlib.metadata.distribution('openbexi-spell-source')
    runtime['manifest'] = manifest
    runtime['installed'] = {}
    for name, expected in manifest['artifacts'].items():
        path = next(Path(distribution.locate_file(entry)) for entry in distribution.files
                    if str(entry).endswith('/bin/' + name))
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, name
        runtime['installed'][name] = actual
results['runtime_sources'] = runtime
source = '''from pathlib import Path
from spell.runtime import ARGS, IVARS
from spell.lib.adapter.data import DataContainer, Var
from spell.lang.constants import LONG, STRING
from spell.lang.functions import Pause
import sys
PLAIN = {'count': 3}
NOT_DICTIONARY = 42
def refs():
    return [sys.getrefcount(ARGS), sys.getrefcount(IVARS),
            sys.getrefcount(next(iter(ARGS))), sys.getrefcount(next(iter(IVARS)))]
assert isinstance(ARGS, DataContainer) and isinstance(IVARS, DataContainer)
assert len(ARGS) == 0 and len(IVARS) == 0
Path('container-types.json').write_text(__import__('json').dumps({
    'ARGS': str(type(ARGS)), 'IVARS': str(type(IVARS))}))
for container in (ARGS, IVARS):
    container['count'] = Var(Default=3, Type=LONG, Range=[0,10])
    container['text'] = Var(Default='initial', Type=STRING)
before_refs = refs()
Path('ready.txt').write_text('ready')
Pause()
assert refs() == before_refs, (before_refs, refs())
assert not Path('should-not-evaluate.txt').exists()
assert PLAIN == {'count': 9, 'new': 'plain unicode λ'}
for container in (ARGS, IVARS):
    assert container['count'] == 7
    assert container['text'] == 'café λ'
    assert container['new'] == 42
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
    try:
        result = session.request(identifier, fields)
    except RuntimeError as error:
        prefix = identifier + ': '
        if not str(error).startswith(prefix + '{'):
            raise
        reply = ast.literal_eval(str(error)[len(prefix):])
        if reply.get('ok') is not False or reply.get('message', {}).get('type') != 7:
            raise
        result = reply['message']['fields']
        assert result.get('ErrorMsg'), reply
        result = dict(result, Error=True)
    results['observations'].append(dict(id=identifier, fields=fields, result=result))
    return result


def observe(identifier, dimension, condition, actual, oracle):
    results['checks'][identifier + ':' + dimension] = dict(
        contracts=[], dimension=dimension, passed=bool(condition), actual=actual,
        oracle=oracle, evidence_kind='diagnostic-native-client-editing')


def read(dictionary):
    response = request('REQ_GET_DICTIONARY', {'DictName': dictionary})
    content = response.get('DictContents', '')
    for chunk in range(1, int(response.get('TotalChunks', '0'))):
        content += request('REQ_GET_DICTIONARY', {'DictName': dictionary, 'CurrentChunk': str(chunk)})['DictContents']
    return content


def edit(dictionary, key, expression, format='NONE', confirm='False', **extra):
    response = request('REQ_UPD_DICTIONARY', dict(DictName=dictionary,
        DictContents='\x05'.join([key, expression, format, confirm]), **extra))
    assert not response.get('Error'), response
    return response


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
        original = 'count\x053\x05\x05long\x05[0,10]\x05[]\x05false\x04text\x05initial\x05\x05string\x05[]\x05[]\x05false'
        observe(dictionary, 'positive', response.get('DictContents') == original, response,
                'LRM p.86 original typed ARGS/IVARS are visible to the client with each variable value/type/range/format/confirmation field')
        invalid = request('REQ_UPD_DICTIONARY', {'DictName': dictionary,
            'DictContents': '\x05'.join(['count', repr('bad'), 'NONE', 'False'])})
        observe(dictionary, 'failure', bool(invalid.get('Error')), invalid,
                'Native client assignment of STRING to a declared LONG must return an explicit error without a user prompt')
        failures = [
            ('range', ['count', '11', 'NONE', 'False'], {}),
            ('syntax', ['count', '(', 'NONE', 'False'], {}),
            ('missing-field', ['count', '4', 'NONE'], {}),
            ('extra-field', ['count', '4', 'NONE', 'False', 'extra'], {}),
            ('empty-key', ['', '4', 'NONE', 'False'], {}),
            ('empty-value', ['count', '', 'NONE', 'False'], {}),
            ('bad-format', ['count', '4', 'UNKNOWN', 'False'], {}),
            ('string-format', ['text', "'changed'", 'hex', 'False'], {}),
            ('bad-confirm', ['count', '4', 'NONE', 'maybe'], {}),
            ('bad-merge', ['count', '4', 'NONE', 'False'], {'DictMergeNew': 'maybe'}),
            ('unknown-key', ['missing', '4', 'NONE', 'False'], {}),
            ('unknown-no-eval', ['missing', "__import__('pathlib').Path('should-not-evaluate.txt').write_text('bad')", 'NONE', 'False'], {}),
            ('malformed-no-eval', ['count', "__import__('pathlib').Path('should-not-evaluate.txt').write_text('bad')", 'NONE'], {}),
            ('oversized', ['text', repr('x' * 65536), 'NONE', 'False'], {}),
        ]
        for case, fields, extra in failures:
            failure = request('REQ_UPD_DICTIONARY', dict(DictName=dictionary, DictContents='\x05'.join(fields), **extra))
            unchanged = read(dictionary)
            observe(dictionary + ':' + case, 'failure', failure.get('Error') and unchanged == original,
                    dict(error=failure, unchanged=unchanged == original),
                    'Malformed, incompatible or unapproved client edits return a nonfatal error and retain existing values and metadata')
        for value in ('0', '10'):
            edit(dictionary, 'count', value, 'hex', 'True')
            fields = read(dictionary).split('\x04')[0].split('\x05')
            observe(dictionary + ':range-' + value, 'boundary', fields == ['count', value, 'hex', 'long', '[0,10]', '[]', 'true'], fields,
                    'Range endpoints are accepted and HEX/confirmation metadata reaches the client without an unsolicited prompt')
        edit(dictionary, 'text', "''")
        observe(dictionary + ':empty-string', 'boundary', read(dictionary).split('\x04')[1].split('\x05')[1] == '',
                read(dictionary), 'An empty STRING value is distinct from a malformed empty expression')
        edit(dictionary, 'text', repr('x' * 12000))
        large = read(dictionary)
        observe(dictionary + ':chunks', 'boundary', large.split('\x04')[1].split('\x05')[1] == 'x' * 12000,
                dict(length=len(large)), 'Large dictionary values round-trip through the original chunk protocol')
        for chunk in ('-1', 'abc', '1suffix', '999999999999999999999999999999'):
            failure = request('REQ_GET_DICTIONARY', {'DictName': dictionary, 'CurrentChunk': chunk})
            observe(dictionary + ':chunk-' + chunk, 'failure', failure.get('Error'), failure,
                    'Malformed or out-of-range chunk identifiers return an explicit nonfatal error')
        unicode_value = ('λ€' + chr(0x1F680)) * 2500
        edit(dictionary, 'text', repr(unicode_value))
        unicode_read = read(dictionary)
        observe(dictionary + ':unicode-chunks', 'boundary', unicode_read.split('\x04')[1].split('\x05')[1] == unicode_value,
                dict(length=len(unicode_read)), 'Large UTF-8 values retain complete code points at chunk boundaries')
        for name, value in [('count', '7'), ('text', repr('café λ'))]:
            response = request('REQ_UPD_DICTIONARY', {'DictName': dictionary,
                'DictContents': '\x05'.join([name, value, 'NONE', 'False'])})
            assert not response.get('Error'), response
        response = request('REQ_GET_DICTIONARY', {'DictName': dictionary})
        updated = 'count\x057\x05\x05long\x05[0,10]\x05[]\x05false\x04text\x05café λ\x05\x05string\x05[]\x05[]\x05false'
        observe(dictionary, 'boundary', response.get('DictContents') == updated, response,
                'Actual client editing preserves Unicode text and native typed field metadata')
        observe(dictionary, 'recovery', response.get('DictContents') == updated, response,
                'An invalid assignment followed by valid edits leaves both original native containers usable and exposes the new values')
        no_stale = request('REQ_GET_DICTIONARY', {'DictName': dictionary, 'CurrentChunk': '0'})
        observe(dictionary + ':stale-chunk', 'failure', no_stale.get('Error'), no_stale,
                'Reading a new small dictionary invalidates cached chunks from earlier large values')
        edit(dictionary, 'new', '6 * 7', DictMergeNew='True')
        observe(dictionary + ':merge-expression', 'positive', read(dictionary).endswith('new\x0542\x05\x05long\x05[]\x05[]\x05false'), read(dictionary),
                'Explicit merge creates a native variable and preserves original Development expression evaluation')
        for _ in range(30):
            read(dictionary)
            edit(dictionary, 'count', '7')
    for dictionary in ('MISSING', 'NOT_DICTIONARY'):
        response = request('REQ_UPD_DICTIONARY', {'DictName': dictionary, 'DictContents': 'count\x054'})
        observe(dictionary, 'failure', response.get('Error'), response, 'Missing and unsupported dictionary targets explicitly fail')
    for key, value in [('count', '9'), ('new', repr('plain unicode λ'))]:
        response = request('REQ_UPD_DICTIONARY', {'DictName': 'PLAIN', 'DictContents': key + '\x05' + value})
        observe('PLAIN:' + key, 'positive', not response.get('Error'), response, 'Original ordinary dictionary updates continue to work')
    session.request('CMD_RUN', send=True)
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        drain()
        status = session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
        if status in ('FINISHED', 'ERROR', 'ABORTED'):
            results['resumed_status'] = status
            drain()
            break
        time.sleep(.02)
    else:
        raise TimeoutError('Native executor did not finish after editing')
    results['continued_after_edits'] = (project/'complete.txt').exists()
    observe('resume', 'recovery', status == 'FINISHED' and results['continued_after_edits'],
            dict(status=status, completed=results['continued_after_edits']),
            'The native procedure reads edited values, proves stable key/container reference counts, then writes and completes')
    items = [event.get('message', {}).get('fields', {}) for event in events
             if event.get('message', {}).get('id') == 'MSG_NOTIFICATION']
    restored = [fields for fields in items if fields.get('DataType') == 'ITEM'
                and fields.get('ItemName') == 'count' and fields.get('ItemValue') == '8']
    observe('notifications', 'recovery', [item['ItemStatus'] for item in restored] == ['IN PROGRESS', 'SUCCESS', 'SUCCESS'] * 2, restored,
            'Each container emits assignment progress/success and read success after notification settings are restored')
    results['passed'] = (status == 'FINISHED' and results['continued_after_edits']
                         and all(row['passed'] for row in results['checks'].values()))
finally:
    if session.log:
        session.log.flush()
        session.log.seek(0)
        (project/'native.log').write_text(session.log.read(), encoding='utf-8')
    try:
        session.close()
    finally:
        results['runtime_host_sha256'] = hashlib.sha256(Path('/opt/host/native.py').read_bytes()).hexdigest()
        (project/'dta-edit-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        (project/'dta-edit-wire.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
