"""Observe original UI IPC and answer prompts as an independent native client."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0, '/opt/host')
from native import NativeSession

runtime = {'native.py': hashlib.sha256(Path('/opt/host/native.py').read_bytes()).hexdigest()}
manifest_path = next((path for path in (Path('/opt/dta-native-patch/manifest.json'),
    Path('/opt/combined-native-patch/manifest.json'),
    Path('/opt/ui-native-patch/manifest.json')) if path.exists()), Path('/nonexistent-ui-manifest'))
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text())
    distribution = importlib.metadata.distribution('openbexi-spell-source')
    runtime['ui_manifest'] = manifest
    runtime['installed'] = {}
    for name, expected in manifest['artifacts'].items():
        path = next(Path(distribution.locate_file(entry)) for entry in distribution.files
                    if str(entry).endswith('/bin/' + name))
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, (name, actual, expected)
        runtime['installed'][name] = actual
Path('ui-runtime.json').write_text(json.dumps(runtime, indent=2), encoding='utf-8')

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
        message = event.get('message', {})
        if message.get('id') == 'MSG_PROMPT':
            pending.append(message)


try:
    session.start()
    session.pump = drain
    session.request('CMD_RUN', send=True)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        drain()
        while pending:
            fields = pending.pop(0)['fields']
            active = json.loads(Path('ui-active.json').read_text())
            match = [row for row in active['prompts'] if row['text'] == fields['Text']]
            assert len(match) == 1, (active, fields)
            expected = match[0]
            actual = fields.get('ExpectedValues', '').split('\x04') if fields.get('ExpectedValues') else []
            assert actual == expected['choices'], (expected, fields)
            answers.append(dict(check=active['id'], fields=fields, answer=expected['answer']))
            session.request('MSG_ANSWER', {'ReturnValue': expected['answer']}, send=True)
        status = session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
        drain()
        if status in ('FINISHED', 'ERROR', 'ABORTED'):
            assert status == 'FINISHED', status
            break
        time.sleep(.02)
    else:
        raise TimeoutError('UI conformance did not finish')
finally:
    session.close()
    Path('ui-wire.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
    Path('ui-answers.json').write_text(json.dumps(answers, indent=2), encoding='utf-8')

import importlib.util
edge_spec = importlib.util.spec_from_file_location('ui_edge_controller', '/workspace/ui_edge_controller.py')
edge_module = importlib.util.module_from_spec(edge_spec)
edge_spec.loader.exec_module(edge_module)
edge_module.run()
