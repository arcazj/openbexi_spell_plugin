"""Observe original IPC without supplying the timed default from the client."""
import hashlib
import json
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0, '/opt/host')
from native import NativeSession
sys.path.insert(0, '/workspace')
from installed_provenance import capture
from prompt_timeout_cases import CASES

runtime = capture()
Path('/workspace/runtime.json').write_text(json.dumps(runtime, indent=2) + '\n')
checks = {}
for name, spec in CASES.items():
    project = Path('/workspace') / name.replace(':', '-')
    project.mkdir()
    (project / 'main.py').write_text(spec['source'], encoding='utf-8')
    session = NativeSession(project, project / 'main.py', {})
    events, prompts, answers = [], [], []
    row = {'passed': False, 'dimension': spec['dimension'],
           'contracts': ['CMP-LRM244-EXAMPLE-118'],
           'oracle': 'LRM 2.4.4 pp.71-72: positive native timed default; zero or omitted timeout requires explicit answer; malformed timeout raises SyntaxException; subsequent timed default recovers.',
           'source': spec['source'], 'prompts': prompts, 'answers': answers}

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
                prompts.append({'fields': message['fields'], 'received': time.monotonic()})

    try:
        session.start()
        session.pump = drain
        session.request('CMD_RUN', send=True)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            drain()
            status = session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
            drain()
            if spec.get('no_prompt'):
                assert not prompts, prompts
            if prompts and 'reply' in spec and not answers:
                assert len(prompts) == 1, prompts
                assert status == 'PROMPT', status
                assert not (project / 'result.json').exists()
                if time.monotonic() - prompts[0]['received'] >= spec['hold']:
                    session.request('MSG_ANSWER', {'ReturnValue': spec['reply']}, send=True)
                    answers.append(spec['reply'])
            if status in ('FINISHED', 'ERROR', 'ABORTED'):
                row['status'] = status
                assert status == 'FINISHED', status
                break
            time.sleep(.01)
        else:
            raise TimeoutError('Native timed prompt did not return within five seconds')
        if spec.get('rejected'):
            assert (project / 'rejected.txt').read_text() == 'SyntaxException'
        if 'answer' in spec:
            result = json.loads((project / 'result.json').read_bytes())
            row['result'] = result
            assert result['answer'] == spec['answer'], result
            assert len(prompts) == 1, prompts
            default = prompts[0]['fields']['Default']
            if 'wire_default' in spec:
                assert default == spec['wire_default'], prompts
            else:
                assert default in ('A', 'B'), prompts
        if 'reply' in spec:
            assert answers == [spec['reply']], answers
        else:
            assert not answers
        row['passed'] = True
    except Exception as error:
        row['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        if session.log:
            session.log.flush()
            session.log.seek(0)
            (project / 'native.log').write_text(session.log.read(), encoding='utf-8')
        try:
            session.close()
        except Exception as error:
            row['passed'] = False
            row['cleanup_error'] = type(error).__name__ + ': ' + str(error)
        (project / 'events.json').write_text(json.dumps(events, indent=2) + '\n')
        row['events_sha256'] = hashlib.sha256((project / 'events.json').read_bytes()).hexdigest()
        checks[name] = row
        Path('/workspace/checks.json').write_text(json.dumps(checks, indent=2) + '\n')
        print(name, row['passed'], row.get('error', ''), flush=True)
raise SystemExit(not all(row['passed'] for row in checks.values()))
