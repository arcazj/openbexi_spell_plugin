"""Independent client for native DTA value prompts and actual ITEM messages."""
import json
import hashlib
import importlib.metadata
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0, '/opt/host')
from native import NativeSession

runtime = {'host_sha256': hashlib.sha256(Path('/opt/host/native.py').read_bytes()).hexdigest()}
manifest_path = Path('/opt/dta-native-patch/manifest.json')
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_bytes())
    installed = importlib.metadata.distribution('openbexi-spell-source')
    runtime['manifest'] = manifest
    runtime['artifacts'] = {}
    for name, expected in manifest['artifacts'].items():
        target = next(Path(installed.locate_file(entry)) for entry in installed.files
                      if str(entry).endswith('/bin/' + name))
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual == expected, (name, expected, actual)
        runtime['artifacts'][name] = actual
Path('dta-runtime.json').write_text(json.dumps(runtime, indent=2), encoding='utf-8')

events, observations, pending = [], [], []
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
        message = event.get('message', {})
        if message.get('id') == 'MSG_PROMPT':
            pending.append(message)


try:
    session.start()
    session.pump = drain
    session.request('CMD_RUN', send=True)
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        drain()
        while pending:
            fields = pending.pop(0)['fields']
            active = json.loads(Path('dta-active.json').read_text())
            previous = sum(row['check'] == active['id'] for row in observations)
            expected = active['prompts'][previous]
            actual = fields.get('ExpectedValues', '').split('\x04') if fields.get('ExpectedValues') else []
            observed = dict(check=active['id'], fields=fields, expected=expected)
            observations.append(observed)
            assert expected['contains'].lower() in fields['Text'].lower(), (expected, fields)
            assert actual == expected['choices'], (expected, fields)
            session.request('MSG_ANSWER', {'ReturnValue': expected['answer']}, send=True)
        status = session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
        drain()
        if status in ('FINISHED', 'ERROR', 'ABORTED'):
            assert status == 'FINISHED', status
            break
        time.sleep(.02)
    else:
        raise TimeoutError('Native DTA contracts did not finish')
finally:
    session.close()
    Path('dta-wire.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
    Path('dta-answers.json').write_text(json.dumps(observations, indent=2), encoding='utf-8')
