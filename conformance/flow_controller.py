"""Independent controller observes original IPC and drives real native actions."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0, '/opt/host')
from native import NativeSession

descriptions = json.loads(Path('/workspace/scenarios.json').read_text())
results = {}
for name, specification in descriptions.items():
    project = Path('/workspace') / name
    project.mkdir(exist_ok=True)
    (project / 'main.py').write_text(specification['source'], encoding='utf-8')
    events, pauses, action_states = [], [], []
    session = NativeSession(project, project / 'main.py', {})
    result = {'passed': False, 'status': None, 'pauses': pauses, 'action_states': action_states}

    def drain():
        while True:
            try:
                event = session.events.get_nowait()
            except queue.Empty:
                break
            events.append(event)
            if event.get('event') == 'connectionError':
                raise RuntimeError(event)

    try:
        try:
            session.start()
        except RuntimeError as error:
            result['startup_error'] = str(error)
            if specification['status'] == 'ERROR' and 'could not open' in str(error):
                result['status'] = 'ERROR'
                result['passed'] = True
            else:
                raise
        else:
            session.pump = drain
            session.request('CMD_RUN', send=True)
            deadline = time.monotonic() + 35
            running_action_sent = False
            while time.monotonic() < deadline:
                drain()
                status = session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
                drain()
                if status in ('FINISHED', 'ERROR', 'ABORTED'):
                    result['status'] = status
                    assert status == specification['status'], (name, status, specification['status'])
                    break
                if (specification.get('running_action') and not running_action_sent
                        and status == 'RUNNING' and (project / 'ready.txt').exists()):
                    result['running_action_info'] = session.request('REQ_EXEC_INFO', context=True)
                    session.request('CMD_ACTION', send=True)
                    running_action_sent = True
                if status == 'PAUSED' and (project / 'stage.txt').exists():
                    stage = (project / 'stage.txt').read_text()
                    if stage not in pauses:
                        pauses.append(stage)
                        info = session.request('REQ_EXEC_INFO', context=True)
                        if 'actions' in specification:
                            session.request('CMD_ACTION', send=True)
                            expected = specification['actions'][stage]
                            until = time.monotonic() + 2
                            while time.monotonic() < until:
                                drain()
                                session.request('REQ_EXEC_STATUS')
                                observed = (project / 'actions.txt').read_text().splitlines()
                                if observed == expected:
                                    time.sleep(.12)
                                    drain()
                                    break
                                time.sleep(.02)
                            observed = (project / 'actions.txt').read_text().splitlines()
                            action_states.append(dict(stage=stage, info=info, effects=observed))
                            assert observed == expected, (stage, observed, expected)
                        else:
                            # A real pause must prevent effects until explicit
                            # resume. A second status read forms a positive
                            # observation while the procedure is quiescent.
                            assert not (project / 'effects.json').exists()
                            assert session.request('REQ_EXEC_STATUS').get('ExecutorStatus') == 'PAUSED'
                        session.request('CMD_RUN', send=True)
                time.sleep(.01)
            else:
                raise TimeoutError('Native FLOW scenario did not finish: ' + name)
            if 'effects' in specification:
                result['effects'] = json.loads((project / 'effects.json').read_text())
                assert result['effects'] == specification['effects'], result['effects']
            if 'pauses' in specification:
                assert pauses == specification['pauses'], pauses
            if 'actions' in specification:
                assert pauses == list(specification['actions']), pauses
            if specification.get('running_action'):
                assert running_action_sent
            result['passed'] = True
        if specification.get('no_continue'):
            assert not (project / 'continued.txt').exists(), 'Executed after terminal/jump failure'
        if 'cleanup' in specification:
            result['cleanup'] = (project / 'cleanup.txt').read_text()
            assert result['cleanup'] == specification['cleanup']
    except Exception as error:
        result.update(passed=False, error=type(error).__name__ + ': ' + str(error))
    finally:
        try:
            drain()
        except Exception as error:
            result.update(passed=False, drain_error=str(error))
        if session.log:
            session.log.flush()
            session.log.seek(0)
            (project / 'native.log').write_text(session.log.read(), encoding='utf-8')
        result['asrun'] = {str(path.relative_to(Path(session.directory.name))): path.read_text(errors='replace')
                           for path in Path(session.directory.name).rglob('*')
                           if path.is_file() and path.suffix.lower() in ('.asrun', '.ar')}
        try:
            session.close()
        except Exception as error:
            result.update(passed=False, cleanup_error=str(error))
        result['events'] = events
        results[name] = result
        Path('/workspace/observations.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
        print(name, result['passed'], result.get('error', result['status']), flush=True)

sys.path.insert(0, '/workspace')
from installed_provenance import capture
Path('/workspace/runtime.json').write_text(json.dumps({
    'integrated': capture(),
    'native_session_sha256': hashlib.sha256(Path('/opt/host/native.py').read_bytes()).hexdigest(),
    'interpreter': sys.version,
    'installed': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (
        Path('/usr/local/lib/python3.13/site-packages/spell_native/bin/libspell_executor313.so'),
        Path('/usr/local/lib/python3.13/site-packages/spell/lang/helpers/exechelper.py'))},
}, indent=2) + '\n')
