"""Independent actual native IPC observer for the Notify spelling and modifier."""
import json
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0, '/opt/host')
from native import NativeSession
sys.path.insert(0, '/workspace')
from notification_provenance import capture_notification

Path('notification-runtime.json').write_text(json.dumps(capture_notification(), indent=2))
events, answers, pending = [], [], []
session = NativeSession('/workspace', '/workspace/main.py', {})


def drain():
    while True:
        try:
            event = session.events.get_nowait()
        except queue.Empty:
            return
        events.append(event)
        if event.get('event') == 'connectionError':
            raise RuntimeError(event)
        if event.get('message', {}).get('id') == 'MSG_PROMPT':
            pending.append(event['message'])


try:
    session.start()
    session.pump = drain
    session.request('CMD_RUN', send=True)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        drain()
        while pending:
            fields = pending.pop(0)['fields']
            active = json.loads(Path('notification-active.json').read_text())
            expected, = [p for p in active['prompts'] if p['text'] == fields['Text']]
            answers.append(dict(check=active['id'], fields=fields, answer=expected['answer']))
            session.request('MSG_ANSWER', {'ReturnValue': expected['answer']}, send=True)
        status = session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
        drain()
        if status in ('FINISHED', 'ERROR', 'ABORTED'):
            assert status == 'FINISHED', status
            break
        time.sleep(.02)
    else:
        raise TimeoutError('Notify conformance did not finish')
finally:
    session.close()
    Path('notification-wire.json').write_text(json.dumps(events, indent=2))
    Path('notification-answers.json').write_text(json.dumps(answers, indent=2))

from notification_checkpoint import run
run()

if '--ui-regression' in sys.argv:
    from notification_ui_regression import run
    run()
