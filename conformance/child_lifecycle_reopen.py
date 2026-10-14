"""Four serialized native child removals followed by explicit child startup.

This is an actual context/executor IPC oracle, not a concurrent lifecycle claim.
No child-startup service or prompt auto-answering runs in this controller.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import time
import traceback


ROOT = Path('/workspace')
FORBIDDEN_HOST_EVENTS = {'childRequest', 'childRequestRejected', 'unsupportedRequest'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(operation, phase):
    """Append-only markers expose repeated execution instead of overwriting it."""
    assert operation in ('close', 'kill') and phase in ('prompt', 'finished')
    def mark(filename, text):
        # No live file handle is left in the traced procedure's local state.
        return ("Path(%r).write_text((Path(%r).read_text() if Path(%r).exists() else '') + %r)\n"
                % (filename, filename, filename, text + '\n'))
    first = """from pathlib import Path
from spell.lang.functions import Prompt
from spell.lang.constants import ALPHA
"""
    first += mark('first-start.txt', 'start')
    if phase == 'prompt':
        first += "assert Prompt('FIRST_HOLD', Type=ALPHA)=='release-first'\n"
    first += mark('first-finish.txt', 'finished')
    second = """from pathlib import Path
from spell.lang.functions import Prompt
from spell.lang.constants import ALPHA
"""
    second += mark('second-start.txt', 'start')
    second += "assert Prompt('SECOND_HOLD', Type=ALPHA)=='release-second'\n"
    second += mark('second-finish.txt', 'finished')
    parent = """import json
from pathlib import Path
from spell.lang.functions import StartProc, Prompt
from spell.lang.constants import ALPHA
from spell.lib.registry import REGISTRY
assert StartProc('first', Automatic=False, Blocking=False, HandleError=False) is True
assert Prompt('PARENT_FIRST_READY', Type=ALPHA)=='remove-first'
result=REGISTRY['EXEC'].%sSubProcedure()
assert result is True
Path('operation-result.json').write_text(json.dumps({'returned':result}))
assert StartProc('second', Automatic=False, Blocking=False, HandleError=False) is True
assert Prompt('PARENT_SECOND_READY', Type=ALPHA)=='finish-parent'
""" % operation
    parent += mark('parent-finish.txt', 'finished')
    return {'main.py': parent, 'first.py': first, 'second.py': second}


def marker_snapshot(project):
    return {name: (project/name).read_text().splitlines() if (project/name).exists() else []
            for name in ('first-start.txt', 'first-finish.txt', 'second-start.txt',
                         'second-finish.txt', 'parent-finish.txt')}


def run_case(session_type, operation, phase):
    name = operation + '-' + phase
    project = ROOT / name
    project.mkdir()
    for filename, source in sources(operation, phase).items():
        (project/filename).write_text(source, encoding='utf-8')
    session = session_type(project, project/'main.py', {})
    row = {'passed': False, 'operation': operation, 'first_phase': phase,
           'events': [], 'commands': [], 'checkpoints': [], 'answers': [],
           'procedure_inputs': {filename: sha(project/filename)
                                for filename in ('main.py', 'first.py', 'second.py')}}
    events = row['events']
    answered = set()
    ran = set()

    def drain():
        while True:
            try:
                event = session.events.get_nowait()
            except queue.Empty:
                return
            events.append(event)
            if event.get('event') in {'connectionError', *FORBIDDEN_HOST_EVENTS}:
                raise RuntimeError('Unexpected native host event: ' + str(event))

    def wait_for(predicate, label, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            drain()
            if predicate():
                return
            time.sleep(.025)
        raise TimeoutError(name + ': ' + label)

    def status(procedure):
        return session.request('REQ_EXEC_STATUS', procedure=procedure).get('ExecutorStatus')

    def expect_status(procedure, expected):
        def reached():
            actual = status(procedure)
            if actual in {'ERROR', 'ABORTED'}:
                raise AssertionError((procedure, actual, expected))
            return actual == expected
        wait_for(reached, procedure + ' status ' + expected)

    def opened(basename):
        return {message['fields']['ProcId']
                for event in events
                for message in (event.get('message', {}),)
                if message.get('id') == 'MSG_EXEC_OP'
                and message.get('fields', {}).get('ExecOp') == 'OPEN'
                and message['fields'].get('ParentId') == session.instance
                and message['fields'].get('ProcId', '').split('#')[0] == basename}

    def child_id(basename):
        wait_for(lambda: bool(opened(basename)), basename + ' OPEN notification')
        instances = opened(basename)
        assert len(instances) == 1, instances
        instance, = instances
        assert instance != session.instance and '#' in instance, instance
        return instance

    def prompt(procedure, text):
        def matches():
            return [event['message'] for event in events
                    if event.get('message', {}).get('id') == 'MSG_PROMPT'
                    and event['message'].get('fields', {}).get('ProcId') == procedure
                    and event['message']['fields'].get('Text') == text]
        wait_for(lambda: bool(matches()), procedure + ' prompt ' + text)
        observed = matches()
        assert len(observed) == 1, observed
        assert observed[0].get('sender') == procedure, observed[0]
        expect_status(procedure, 'PROMPT')
        return observed[0]

    def answer(procedure, text, value):
        observed = prompt(procedure, text)
        key = (procedure, text)
        assert key not in answered, key
        # Mark before the send: an uncertain answer is never replayed.
        answered.add(key)
        row['answers'].append({'procedure': procedure, 'prompt': observed, 'value': value})
        session.request('MSG_ANSWER', {'ReturnValue': value}, send=True, procedure=procedure)

    def run(procedure):
        assert procedure not in ran, procedure
        expect_status(procedure, 'PAUSED')
        # Every Run is explicit and issued once, including on an uncertain reply.
        ran.add(procedure)
        row['commands'].append({'id': 'CMD_RUN', 'procedure': procedure})
        session.request('CMD_RUN', send=True, procedure=procedure)

    def checkpoint(label, present, absent=()):
        inventory = session.request('REQ_EXEC_LIST', context=True)
        remaining = set(filter(None, inventory['ExecutorList'].split('\x03')))
        assert set(present) <= remaining and not set(absent) & remaining, inventory
        info = {procedure: session.request('REQ_EXEC_INFO', context=True, procedure=procedure)
                for procedure in present}
        observation = {'label': label, 'executor_list': inventory, 'executors': info,
                       'markers': marker_snapshot(project), 'event_offset': len(events)}
        row['checkpoints'].append(observation)
        return observation

    log_copy = None
    owned = []
    reader_threads = []
    try:
        session.start()
        row['parent_id'] = session.instance
        session.pump = drain
        run(session.instance)
        first = row['first_child_id'] = child_id('first')
        prompt(session.instance, 'PARENT_FIRST_READY')
        expect_status(first, 'PAUSED')
        initial = checkpoint('first-paused', (session.instance, first))
        assert not any(initial['markers'].values()), initial
        assert initial['executors'][first].get('OpenMode') == '{Automatic:False,Visible:True,Blocking:False}'
        run(first)
        if phase == 'prompt':
            prompt(first, 'FIRST_HOLD')
        else:
            expect_status(first, 'FINISHED')
        before = checkpoint('first-' + phase, (session.instance, first))
        assert before['markers']['first-start.txt'] == ['start'], before
        first_finished = [] if phase == 'prompt' else ['finished']
        assert before['markers']['first-finish.txt'] == first_finished, before
        answer(session.instance, 'PARENT_FIRST_READY', 'remove-first')
        wait_for(lambda: any(event.get('message', {}).get('id') == 'MSG_EXEC_OP'
                 and event['message'].get('fields', {}).get('ProcId') == first
                 and event['message']['fields'].get('ExecOp') == operation.upper()
                 for event in events), 'actual old-child removal notification')
        second = row['second_child_id'] = child_id('second')
        assert second != first, (first, second)
        prompt(session.instance, 'PARENT_SECOND_READY')
        expect_status(second, 'PAUSED')
        assert json.loads((project/'operation-result.json').read_bytes()) == {'returned': True}
        row['operation_result'] = json.loads((project/'operation-result.json').read_bytes())
        paused = checkpoint('replacement-paused', (session.instance, second), (first,))
        assert paused['executors'][second].get('OpenMode') == '{Automatic:False,Visible:True,Blocking:False}'
        assert paused['markers']['first-start.txt'] == ['start'], paused
        assert paused['markers']['first-finish.txt'] == first_finished, paused
        assert not paused['markers']['second-start.txt'] and not paused['markers']['second-finish.txt'], paused
        # Drain another real round trip while both procedures deliberately hold.
        # No sleep-based auto-resume or queued prompt answer can advance either.
        expect_status(session.instance, 'PROMPT')
        expect_status(second, 'PAUSED')
        assert marker_snapshot(project) == paused['markers']
        run(second)
        prompt(second, 'SECOND_HOLD')
        held = checkpoint('replacement-prompt', (session.instance, second), (first,))
        assert held['markers']['second-start.txt'] == ['start'], held
        assert held['markers']['second-finish.txt'] == [], held
        assert held['markers']['parent-finish.txt'] == [], held
        answer(second, 'SECOND_HOLD', 'release-second')
        expect_status(second, 'FINISHED')
        completed = checkpoint('replacement-finished-parent-held', (session.instance, second), (first,))
        assert completed['executors'][session.instance]['ExecutorStatus'] == 'PROMPT', completed
        assert completed['markers']['second-start.txt'] == ['start'], completed
        assert completed['markers']['second-finish.txt'] == ['finished'], completed
        assert completed['markers']['parent-finish.txt'] == [], completed
        answer(session.instance, 'PARENT_SECOND_READY', 'finish-parent')
        expect_status(session.instance, 'FINISHED')
        final = checkpoint('both-finished', (session.instance, second), (first,))
        assert all(info['ExecutorStatus'] == 'FINISHED' for info in final['executors'].values()), final
        assert final['markers'] == {'first-start.txt': ['start'], 'first-finish.txt': first_finished,
            'second-start.txt': ['start'], 'second-finish.txt': ['finished'],
            'parent-finish.txt': ['finished']}, final
        drain()
        assert opened('first') == {first} and opened('second') == {second}
        assert ran == {session.instance, first, second}, ran
        assert answered == {(session.instance, 'PARENT_FIRST_READY'),
                            (session.instance, 'PARENT_SECOND_READY'), (second, 'SECOND_HOLD')}, answered
        # Old-child close/error notifications are valid. They must not corrupt
        # the parent or the replacement's status, including transient failures.
        bad = [event for event in events
               if event.get('message', {}).get('fields', {}).get('ProcId') in {session.instance, second}
               and (event['message']['fields'].get('ExecutorStatus') in {'ERROR', 'ABORTED'}
                    or event['message']['fields'].get('ExecOp') in {'CLOSE', 'KILL', 'CRASH'})]
        assert not bad, bad
        row['passed'] = True
    except Exception:
        row['error'] = traceback.format_exc()
    finally:
        try:
            drain()
        except Exception:
            row['drain_error'] = traceback.format_exc()
            row['passed'] = False
        try:
            # Keep the inode open through NativeSession.close(), which removes
            # its temporary directory. Shutdown diagnostics remain evidence.
            if session.log:
                session.log.flush()
                log_copy = os.fdopen(os.dup(session.log.fileno()), 'rb')
        except Exception:
            row['log_preservation_error'] = traceback.format_exc()
            row['passed'] = False
        try:
            owned = [process for process in (session.process,
                     getattr(session.context, 'process', None),
                     getattr(session.listener, 'process', None)) if process is not None]
            reader_threads = [peer.thread for peer in (session.context, session.listener) if peer is not None]
            session.close()
            row['cleanup'] = {'process_exit_codes': {str(process.pid): process.poll() for process in owned},
                              'reader_threads_alive': [thread.is_alive() for thread in reader_threads]}
            assert all(process.poll() is not None for process in owned), row['cleanup']
            assert not any(thread.is_alive() for thread in reader_threads), row['cleanup']
        except Exception:
            row['cleanup_error'] = traceback.format_exc()
            row['passed'] = False
        finally:
            if log_copy is not None:
                try:
                    log_copy.seek(0)
                    diagnostic = log_copy.read()
                    (project/'native.log').write_bytes(diagnostic)
                    row['native_log_sha256'] = sha(project/'native.log')
                    if any(token in diagnostic for token in (b'AddressSanitizer:', b'runtime error:',
                                                             b'LeakSanitizer:', b'ThreadSanitizer:')):
                        row['sanitizer_error'] = True
                        row['passed'] = False
                except Exception:
                    row['log_capture_error'] = traceback.format_exc()
                    row['passed'] = False
                finally:
                    log_copy.close()
        row['markers'] = marker_snapshot(project)
    return row


def main():
    assert not sys.argv[1:], sys.argv[1:]
    sys.path.insert(0, '/opt/host')
    sys.path.insert(0, '/workspace')
    from native import NativeSession
    if Path('/opt/child-lifecycle-patch').exists():
        from child_lifecycle_provenance import capture
    else:
        from installed_provenance import capture
    report = {'passed': False, 'reopen': True, 'serialized_only': True,
              'implicit_resume': False, 'cases': {}, 'host_inputs': {
                  path.name: sha(path) for path in sorted(Path('/opt/host').glob('*.py'))},
              'runtime_sources': capture()}
    for operation in ('close', 'kill'):
        for phase in ('prompt', 'finished'):
            name = operation + '-' + phase
            row = run_case(NativeSession, operation, phase)
            report['cases'][name] = row
            (ROOT/'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps({'case': name, 'passed': row['passed'], 'error': row.get('error')}), flush=True)
    report['passed'] = len(report['cases']) == 4 and all(row['passed'] for row in report['cases'].values())
    (ROOT/'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return not report['passed']


if __name__ == '__main__':
    raise SystemExit(main())
