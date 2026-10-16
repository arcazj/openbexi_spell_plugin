"""Observe procedure metadata in real native executors."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import time
import traceback

sys.path.insert(0, '/opt/host')
from native import NativeSession
from installed_provenance import capture
from proc_metadata_cases import CASES

ROOT = Path('/workspace')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(ROOT / 'runtime.json').write_text(json.dumps(capture(), indent=2))
(ROOT / 'host-inputs.json').write_text(json.dumps(
    {path.name: sha(path) for path in sorted(Path('/opt/host').glob('*.py'))}, indent=2))
checks = {}
for name, spec in CASES.items():
    project = ROOT / name.replace(':', '-')
    project.mkdir()
    (project / 'main.py').write_text(spec['source'])
    (project / 'plan.json').write_text(json.dumps({'arguments':spec['arguments']}))
    session = NativeSession(project, project / 'main.py', spec['arguments'])
    events = []
    row = dict(passed=False, source=spec['source'], dimension=spec['dimension'], states=[])

    def drain():
        while True:
            try:
                event = session.events.get_nowait()
            except queue.Empty:
                return
            events.append(event)
            if event.get('event') == 'connectionError':
                raise RuntimeError(event)
            assert event.get('message', {}).get('id') != 'MSG_PROMPT', 'Unexpected interactive failure'

    try:
        session.start()
        session.pump = drain
        began = time.monotonic()
        session.request('CMD_RUN', send=True)
        deadline = began + 20
        while time.monotonic() < deadline:
            drain()
            status = session.request('REQ_EXEC_STATUS')['ExecutorStatus']
            if not row['states'] or row['states'][-1]['status'] != status:
                row['states'].append(dict(status=status, elapsed=time.monotonic()-began))
            if status in {'FINISHED', 'ERROR', 'ABORTED'}:
                break
            time.sleep(.01)
        drain()
        row['status'] = status
        if (project/'observed.json').exists(): row['observed']=json.loads((project/'observed.json').read_bytes())
        assert status == 'FINISHED', status
        if spec['waiting']:
            assert any(state['status'] == 'WAITING' for state in row['states']), row['states']
        row['result'] = json.loads((project / 'result.json').read_bytes())
        row['passed'] = True
    except Exception:
        row['error'] = traceback.format_exc()
    finally:
        if session.log:
            session.log.flush()
            session.log.seek(0)
            log = session.log.read()
            (project / 'native.log').write_text(log)
            row['native_log_sha256'] = sha(project / 'native.log')
            if 'AddressSanitizer:' in log or 'runtime error:' in log:
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
