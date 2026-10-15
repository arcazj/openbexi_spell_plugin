"""Diagnostic: child close/kill must target the instance it opened."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import time
import traceback

sys.path.insert(0, '/opt/host')
sys.path.insert(0, '/workspace')
from children import ChildProcedures
from native import NativeSession
if Path('/opt/child-lifecycle-patch').exists():
    from child_lifecycle_provenance import capture
else:
    from installed_provenance import capture

ROOT = Path('/workspace')
rejection = sys.argv[1:] == ['--expect-host-rejection']
removed = sys.argv[1:] == ['--externally-removed']
assert not sys.argv[1:] or rejection or removed
report = {'passed': False, 'expect_host_rejection': rejection,
          'externally_removed': removed, 'cases': {}, 'host_inputs': {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(Path('/opt/host').glob('*.py'))}, 'runtime_sources': capture()}
for operation in ('close', 'kill'):
    for phase in (('prompt', 'finished') if rejection or removed else ('prompt', 'finished', 'none')):
        name = operation + '-' + phase
        project = ROOT / name
        project.mkdir()
        child = "from pathlib import Path\n"
        if phase == 'prompt':
            child += "from spell.lang.functions import Prompt\nfrom spell.lang.constants import ALPHA\nPrompt('CHILD_HOLD', Type=ALPHA)\n"
        child += "Path('child-result.txt').write_text('finished')\n"
        (project/'child.py').write_text(child)
        main = project/'main.py'
        source = """import json
from pathlib import Path
from spell.lang.functions import StartProc, Prompt
from spell.lang.constants import ALPHA
from spell.lib.registry import REGISTRY
from spell.lib.exception import DriverException
assert StartProc('child', Blocking=False, HandleError=False) is True
assert Prompt('PARENT_READY', Type=ALPHA)=='continue'
observed=[]
for attempt in range(2):
    try:
        result=REGISTRY['EXEC'].%sSubProcedure()
        observed.append({'returned':result})
    except DriverException as error:
        observed.append({'exception':str(error)})
Path('parent-result.json').write_text(json.dumps(observed))
""" % operation
        if phase == 'none':
            source = source.replace("assert StartProc('child', Blocking=False, HandleError=False) is True",
                                    '# There is no child to close or kill.')
        main.write_text(source)
        session = NativeSession(project, main, {})
        children = ChildProcedures(session.instance)
        events = []
        row = {'passed': False, 'events': events, 'procedure_inputs': {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (main, project/'child.py')}}
        child_id = None

        def drain():
            while True:
                try:
                    event = session.events.get_nowait()
                except queue.Empty:
                    break
                events.append(event)
                if event.get('event') == 'connectionError':
                    raise RuntimeError(event)
                if 'message' in event:
                    children.observe(event['message'])

        def wait_for(predicate, timeout=15):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                drain()
                children.service(session)
                if predicate():
                    return
                time.sleep(.025)
            raise TimeoutError('Native child lifecycle condition: ' + name)

        def instances():
            return {e.get('message', {}).get('fields', {}).get('ProcId') for e in events
                    if e.get('message', {}).get('id') == 'MSG_EXEC_OP'
                    and e['message']['fields'].get('ExecOp') == 'OPEN'
                    and e['message']['fields'].get('ParentId') == session.instance}

        try:
            session.start()
            session.pump = drain
            session.request('CMD_RUN', send=True)
            if phase != 'none':
                wait_for(lambda: bool(instances()))
                child_id, = instances()
                row['child_id'] = child_id
                expected = 'PROMPT' if phase == 'prompt' else 'FINISHED'
                wait_for(lambda: session.request('REQ_EXEC_STATUS', procedure=child_id).get('ExecutorStatus') == expected)
                row['before'] = session.request('REQ_EXEC_INFO', context=True, procedure=child_id)
            wait_for(lambda: session.request('REQ_EXEC_STATUS').get('ExecutorStatus') == 'PROMPT')
            if removed:
                row['external_removal'] = session.request('REQ_'+operation.upper()+'_EXEC',
                                                          context=True, procedure=child_id)
                row['list_after_external_removal'] = session.request('REQ_EXEC_LIST', context=True)
                assert child_id not in row['list_after_external_removal']['ExecutorList'].split('\x03')
            session.request('MSG_ANSWER', {'ReturnValue': 'continue'}, send=True)
            wait_for(lambda: session.request('REQ_EXEC_STATUS').get('ExecutorStatus') in {'FINISHED', 'ERROR', 'ABORTED'})
            row['parent_status'] = session.request('REQ_EXEC_STATUS')
            if (project/'parent-result.json').exists():
                row['parent_result'] = json.loads((project/'parent-result.json').read_bytes())
            if child_id:
                try:
                    row['after'] = session.request('REQ_EXEC_INFO', context=True, procedure=child_id)
                except RuntimeError as error:
                    row['after_error'] = str(error)
            # The context's actual operation notification is independent of the
            # wrapper return value, which can hide a rejected context request.
            if child_id and not rejection:
                wait_for(lambda: any(e.get('message', {}).get('id') == 'MSG_EXEC_OP'
                    and e['message']['fields'].get('ProcId') == child_id
                    and e['message']['fields'].get('ExecOp') == operation.upper()
                    for e in events), timeout=5)
            row['executor_list'] = session.request('REQ_EXEC_LIST', context=True)
            remaining = row['executor_list']['ExecutorList'].split('\x03')
            if rejection:
                assert child_id in remaining, row['executor_list']
                assert row['after']['ExecutorStatus'] == expected
                results = row['parent_result']
                assert len(results) == 2
                assert all('Unsupported host request' in r.get('exception', '') for r in results), results
                requests = [e['message'] for e in events if e.get('event') == 'unsupportedRequest']
                assert len(requests) == 2, requests
                assert all(r['id'] == 'REQ_'+operation.upper()+'_EXEC'
                           and r['sender'] == session.instance
                           and r['fields']['ProcId'] == child_id for r in requests), requests
            else:
                assert child_id not in remaining, row['executor_list']
                if removed:
                    results = row['parent_result']
                    assert len(results) == 2
                    assert all('Child lifecycle request rejected' in result.get('exception', '')
                               and child_id in result['exception'] for result in results), results
                else:
                    assert row.get('parent_result') == [{'returned': True}, {'returned': True}], row
                if phase == 'none':
                    assert not instances()
                    assert not any(e.get('event') in ('childRequest', 'childRequestRejected', 'unsupportedRequest') for e in events)
                assert not any(e.get('event') in ('childRequest', 'childRequestRejected', 'unsupportedRequest') for e in events)
            assert session.instance in remaining, row['executor_list']
            row['parent_after_removal'] = session.request('REQ_EXEC_STATUS')
            assert row['parent_after_removal']['ExecutorStatus'] == 'FINISHED'
            assert row['parent_status']['ExecutorStatus'] == 'FINISHED', row
            if phase == 'prompt':
                assert not (project/'child-result.txt').exists()
            elif phase == 'finished':
                assert (project/'child-result.txt').read_text() == 'finished'
            row['passed'] = True
        except Exception:
            row['error'] = traceback.format_exc()
        finally:
            try:
                drain()
            except Exception:
                row['drain_error'] = traceback.format_exc()
                row['passed'] = False
            if session.log:
                session.log.flush()
                session.log.seek(0)
                (project/'native.log').write_text(session.log.read())
                row['native_log_sha256'] = hashlib.sha256((project/'native.log').read_bytes()).hexdigest()
                diagnostic = (project/'native.log').read_text()
                if 'AddressSanitizer:' in diagnostic or 'runtime error:' in diagnostic:
                    row['sanitizer_error'] = True
                    row['passed'] = False
            try:
                session.close()
            except Exception:
                row['cleanup_error'] = traceback.format_exc()
                row['passed'] = False
            report['cases'][name] = row
            (ROOT/'result.json').write_text(json.dumps(report, indent=2))
            print(json.dumps({'case': name, 'passed': row['passed'], 'error': row.get('error')}), flush=True)
report['passed'] = all(row['passed'] for row in report['cases'].values())
(ROOT/'result.json').write_text(json.dumps(report, indent=2))
raise SystemExit(not report['passed'])
