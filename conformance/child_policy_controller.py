"""Observe native terminal states, parent prompts, quiescence, and recovery effects."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import time
import traceback

sys.path.insert(0, '/opt/host')
from children import ChildProcedures
from native import NativeSession
from installed_provenance import capture
from child_policy_cases import CASES

ROOT = Path('/workspace')
ACTION_NAMES = {'A': 'ABORT', 'R': 'REPEAT', 'K': 'SKIP', 'Q': 'CANCEL'}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(ROOT / 'runtime.json').write_text(json.dumps(capture(), indent=2))
(ROOT / 'host-inputs.json').write_text(json.dumps(
    {path.name: sha(path) for path in sorted(Path('/opt/host').glob('*.py'))}, indent=2))
checks = {}
for name, spec in CASES.items():
    project = ROOT / name
    project.mkdir()
    for file, key in (('main.py', 'parent'), ('child.py', 'child'), ('good.py', 'good')):
        (project / file).write_text(spec[key])
    session = NativeSession(project, project / 'main.py', {})
    children = ChildProcedures(session.instance)
    events, pending = [], []
    row = dict(passed=False, sources={key: spec[key] for key in ('parent', 'child', 'good')},
               prompts=[], answers=[], held=[], terminal_children={})

    def drain():
        while True:
            try:
                event = session.events.get_nowait()
            except queue.Empty:
                return
            events.append(event)
            if event.get('event') in {'connectionError', 'unsupportedRequest', 'childRequestRejected'}:
                raise RuntimeError(event)
            message = event.get('message', {})
            children.observe(message)
            if message.get('id') == 'MSG_PROMPT':
                row['prompts'].append(message['fields'])
                pending.append(message['fields'])
            if message.get('id') == 'MSG_STATUS':
                fields = message['fields']
                if fields.get('ProcId') != session.instance and fields.get('ExecutorStatus') in {'FINISHED', 'ERROR', 'ABORTED'}:
                    row['terminal_children'][fields['ProcId']] = fields['ExecutorStatus']

    try:
        session.start()
        session.pump = drain
        session.request('CMD_RUN', send=True)
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            drain()
            children.service(session)
            while pending:
                fields = pending.pop(0)
                assert not row['answers'], 'Unexpected repeated failure prompt'
                assert fields['ProcId'] == session.instance, 'The parent must handle the child failure'
                choices = [ACTION_NAMES.get(code, code) for code in fields['ExpectedValues'].split('\x04')]
                assert choices == ['ABORT', 'REPEAT', 'SKIP', 'CANCEL'], choices
                assert 'child' in fields['Text'].lower(), fields
                child, = [identifier for identifier in children.children if identifier.startswith('child#')]
                for _ in range(3):
                    held = dict(parent=session.request('REQ_EXEC_STATUS')['ExecutorStatus'],
                        child=session.request('REQ_EXEC_STATUS', procedure=child)['ExecutorStatus'],
                        attempts=int((project / 'attempts.txt').read_text()),
                        parent_returned=(project / 'first-return.json').exists())
                    row['held'].append(held)
                    assert held == dict(parent='PROMPT', child=spec['outcome'], attempts=1, parent_returned=False)
                    time.sleep(.075)
                row['terminal_children'][child] = spec['outcome']
                session.request('MSG_ANSWER', {'ReturnValue': str(choices.index(spec['action']))}, send=True)
                row['answers'].append(spec['action'])
            status = session.request('REQ_EXEC_STATUS')['ExecutorStatus']
            if status in {'FINISHED', 'ERROR', 'ABORTED'}:
                break
            time.sleep(.025)
        drain()
        row['parent_status'] = status
        assert status == spec['expected_parent'], status
        assert row['answers'] == [spec['action']] and len(row['prompts']) == 1
        row['attempts'] = int((project / 'attempts.txt').read_text())
        assert row['attempts'] == spec['expected_attempts']
        assert (project / 'child-completed.txt').exists() is (spec['action'] == 'REPEAT')
        assert (project / 'recovery-completed.txt').exists() is (spec['action'] != 'ABORT')
        if spec['action'] == 'ABORT':
            assert not (project / 'first-return.json').exists() and not (project / 'parent-result.json').exists()
        else:
            row['result'] = json.loads((project / 'parent-result.json').read_bytes())
            assert row['result'] == dict(returned=spec['expected_return'], recovered=True)
            assert json.loads((project / 'first-return.json').read_bytes()) is spec['expected_return']
        row['inventory'] = session.request('REQ_EXEC_LIST', context=True)
        row['live_states'] = {identifier: session.request('REQ_EXEC_STATUS', procedure=identifier)['ExecutorStatus']
            for identifier in filter(None, row['inventory']['ExecutorList'].split('\x03'))}
        assert row['live_states'][session.instance] == spec['expected_parent']
        assert all(status in {'FINISHED', 'ERROR', 'ABORTED'} for status in row['live_states'].values())
        row['passed'] = True
    except Exception:
        row['error'] = traceback.format_exc()
    finally:
        try:
            drain()
        except Exception:
            row.update(passed=False, drain_error=traceback.format_exc())
        if session.log:
            session.log.flush()
            session.log.seek(0)
            diagnostic = session.log.read()
            (project / 'native.log').write_text(diagnostic)
            row['native_log_sha256'] = sha(project / 'native.log')
            if 'AddressSanitizer:' in diagnostic or 'runtime error:' in diagnostic:
                row.update(passed=False, sanitizer_error=True)
        try:
            session.close()
        except Exception:
            row.update(passed=False, cleanup_error=traceback.format_exc())
        (project / 'events.json').write_text(json.dumps(events, indent=2))
        row['events_sha256'] = sha(project / 'events.json')
        checks[name] = row
        (ROOT / 'checks.json').write_text(json.dumps(checks, indent=2))
        print(json.dumps(dict(case=name, passed=row['passed'], error=row.get('error'))), flush=True)
raise SystemExit(not all(row['passed'] for row in checks.values()))
