"""Observe real context discovery, invalid lookup and subsequent procedure runs."""
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path('/workspace')
sys.path[:0] = [str(ROOT), '/opt/host']
from native import Bridge, NativeSession
if Path('/opt/context-snapshot-patch').exists():
    from context_snapshot_provenance import capture
else:
    from installed_provenance import capture

SOURCE = "from pathlib import Path\nPath('startup-result.txt').write_text('STARTUP_SNAPSHOT_PASSED')\n"
runtime = capture()
runtime['host_native_sha256'] = hashlib.sha256(Path('/opt/host/native.py').read_bytes()).hexdigest()
(ROOT / 'runtime.json').write_text(json.dumps(runtime, indent=2))
options = json.loads((ROOT / 'input.json').read_bytes())
observed = []
original_exchange = Bridge.exchange


def exchange(self, identifier, receiver, fields=None, **kwargs):
    result = original_exchange(self, identifier, receiver, fields, **kwargs)
    if identifier == 'REQ_CTX_INFO':
        observed.append(dict(request=fields, response=result))
        if result.get('ContextStatus') == 'RUNNING':
            assert 1 <= int(result['ContextPort']) <= 65535, result
    return result


Bridge.exchange = exchange  # Observation only; request/result bytes are unchanged.
checks = {}
for index in range(options['repeat']):
    name = 'startup-' + str(index).zfill(3)
    folder = ROOT / name
    folder.mkdir()
    script = folder / 'main.py'
    script.write_text(SOURCE, encoding='utf-8')
    session = NativeSession(folder, script, {})
    start = len(observed)
    row = dict(passed=False, procedure_sha256=hashlib.sha256(script.read_bytes()).hexdigest())
    try:
        session.start()
        missing = session.listener.exchange('REQ_CTX_INFO', 'LST', {'ContextName':'missing-context'})
        assert missing['ContextStatus'] == 'ERROR' and missing['ContextPort'] == '0', missing
        current = session.listener.exchange('REQ_CTX_INFO', 'LST', {'ContextName':'example'})
        row.update(missing=missing, current=current)
        assert current['ContextStatus'] == 'RUNNING', current
        assert int(current['ContextPort']) == int(session.context.process.args[1]), current
        session.request('CMD_RUN', send=True)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status = session.request('REQ_EXEC_STATUS')
            if status.get('ExecutorStatus') in ('FINISHED','ERROR','ABORTED'):
                break
            time.sleep(.025)
        row['final'] = status
        assert status['ExecutorStatus'] == 'FINISHED', status
        session.log.flush()
        session.log.seek(0)
        log = session.log.read()
        (folder / 'native.log').write_text(log, encoding='utf-8')
        assert (folder / 'startup-result.txt').read_text() == 'STARTUP_SNAPSHOT_PASSED', 'Procedure effect missing'
        assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
        row.update(passed=True, final=status, missing=missing, current=current)
    except Exception as error:
        row['error'] = repr(error)
        row['traceback'] = traceback.format_exc()
    finally:
        try:
            session.close()
        except Exception as error:
            row.update(passed=False, cleanup_error=repr(error))
        row['observations'] = observed[start:]
        checks[name] = row
        (ROOT / 'checks.json').write_text(json.dumps(checks, indent=2))
        print(json.dumps(dict(case=name, passed=row['passed'])), flush=True)
raise SystemExit(not all(row['passed'] for row in checks.values()))
