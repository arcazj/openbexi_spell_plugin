"""Control two original executors sharing one original native context."""
import json
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0,'/opt/host')
from native import NativeSession
sys.path.insert(0,'/workspace')
from installed_provenance import capture
Path('race-runtime.json').write_text(json.dumps({'integrated':capture()},indent=2)+'\n',encoding='utf-8')

events = []
session = NativeSession('/workspace','/workspace/setup.py',{})
workers = []


def drain():
    while True:
        try:
            event = session.events.get_nowait()
        except queue.Empty:
            return
        events.append(event)
        if event.get('event') == 'connectionError':
            raise RuntimeError(event)


def request(identifier, procedure, fields=None, context=False, send=False):
    return session.context.exchange(identifier,'CTX' if context else procedure,
        dict(fields or {},ProcId=procedure),send=send,pump=drain)


def await_status(procedure, desired):
    deadline = time.monotonic()+30
    while time.monotonic() < deadline:
        drain()
        status = request('REQ_EXEC_STATUS',procedure).get('ExecutorStatus')
        if status == desired:
            return
        assert status not in ('ERROR','ABORTED'), (procedure,status)
        time.sleep(.02)
    raise TimeoutError((procedure,desired,status))


try:
    session.start()
    session.pump = drain
    session.request('CMD_RUN',send=True)
    await_status(session.instance,'FINISHED')
    for identity in (1,2):
        procedure = 'worker#' + str(identity)
        request('REQ_OPEN_EXEC',procedure,dict(GuiMode='CONTROL',
            Arguments=repr({'identity':identity}),OpenMode='{Automatic:True,Visible:True,Blocking:False}'),context=True)
        workers.append(procedure)
        await_status(procedure,'PAUSED')
    for procedure in workers:
        request('CMD_RUN',procedure,send=True)
    deadline = time.monotonic()+30
    while not all(Path('race-ready-'+str(identity)).exists() for identity in (1,2)):
        drain()
        assert time.monotonic() < deadline, 'Workers never reached start barrier'
        time.sleep(.02)
    Path('race-release').write_text('both native executors reached the barrier')
    for procedure in workers:
        await_status(procedure,'FINISHED')
    request('REQ_OPEN_EXEC','inspect#1',dict(GuiMode='CONTROL',Arguments='{}',
        OpenMode='{Automatic:True,Visible:True,Blocking:False}'),context=True)
    workers.append('inspect#1')
    await_status('inspect#1','PAUSED')
    request('CMD_RUN','inspect#1',send=True)
    await_status('inspect#1','FINISHED')
finally:
    for procedure in reversed(workers):
        try:
            request('REQ_CLOSE_EXEC',procedure,context=True)
        except Exception as error:
            events.append({'close_error':str(error),'procedure':procedure})
    session.close()
    Path('race-wire.json').write_text(json.dumps(events,indent=2),encoding='utf-8')
