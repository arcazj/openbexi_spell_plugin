"""Observe original native IPC directly; no notification methods are replaced."""
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

integrated = capture()
runtime = {'native.py': hashlib.sha256(Path('/opt/host/native.py').read_bytes()).hexdigest(),
           'integrated': integrated, 'installed': {}}
if integrated is not None:
    runtime['patch_recipe'] = integrated['manifest']['composition']['python']['recipes']['patches.py']['sha256']
else:
    manifest = json.loads(Path('/opt/common-conformance-patch/manifest.json').read_text())
    runtime['patch_recipe'] = manifest['files']['patches.py']
    for name, digest in manifest['files'].items():
        if name.startswith('patched/'):
            path = Path('/usr/local/lib/python3.13/site-packages')/name.removeprefix('patched/')
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual == digest, name
            runtime['installed'][name] = actual
Path('silence-runtime.json').write_text(json.dumps(runtime, indent=2), encoding='utf-8')

events = []
session = NativeSession('/workspace', '/workspace/main.py', {})


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
    session.start()
    session.pump = drain
    session.request('CMD_RUN', send=True)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        drain()
        status = session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
        drain()
        if status in ('FINISHED', 'ERROR', 'ABORTED'):
            assert status == 'FINISHED', status
            break
        time.sleep(.02)
    else:
        raise TimeoutError('Native silence procedure did not finish')
finally:
    session.close()
    Path('silence-wire.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
