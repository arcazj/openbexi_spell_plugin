"""Real IPC controls for retained error state, recovery, and failing user actions."""
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import time

ROOT=Path('/workspace')
sys.path.insert(0,str(ROOT))
sys.path.insert(0,'/opt/host')
from native import NativeSession
if Path('/opt/checkpoint-identity-patch').exists():
    from checkpoint_identity_provenance import capture
else:
    from installed_provenance import capture
runtime=capture()
runtime['host_native_sha256']=hashlib.sha256(Path('/opt/host/native.py').read_bytes()).hexdigest()
(ROOT/'runtime.json').write_text(json.dumps(runtime,indent=2))
options=json.loads((ROOT/'input.json').read_bytes())
# Configure the genuine generated example before its original listener starts.
# No native/host implementation is replaced; all subsequent calls exec the
# installed launcher. The wrapper only changes this private fixture's mode.
wrapper=ROOT/'configured-bin'
wrapper.mkdir()
(wrapper/'spell-native').write_text("""#!/usr/local/bin/python
import json,os,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
real='/usr/local/bin/spell-native'
if sys.argv[1:2]==['init-example']:
    raw=subprocess.check_output([real,*sys.argv[1:]])
    settings=json.loads(raw)
    p=Path(settings['example'])/'config/contexts/context_example.xml'
    tree=ET.parse(p)
    tree.find("./executor/property[@name='SaveStateMode']").text=os.environ['CHECKPOINT_MODE']
    tree.write(p,encoding='utf-8')
    sys.stdout.buffer.write(raw)
else:
    os.execv(real,[real,*sys.argv[1:]])
""")
(wrapper/'spell-native').chmod(0o755)
os.environ['PATH']=str(wrapper)+os.pathsep+os.environ['PATH']
BODIES={
    'module-error': "int(Path('flag.txt').read_text())\n",
    'named-error': "def operation():\n    return int(Path('flag.txt').read_text())\noperation()\n",
    'nested-error': "def leaf():\n    return int(Path('flag.txt').read_text())\ndef operation():\n    return leaf()\noperation()\n",
    'user-action-error': "def operation():\n    Path('action.txt').write_text('called')\n    raise ValueError('CHECKPOINT_UNCAUGHT')\nSetUserAction(operation,'Failing callback')\nPause()\n",
}
checks={}
for mode in options['modes']:
    os.environ['CHECKPOINT_MODE']=mode
    for case in options['cases']:
        identifier=mode+':'+case
        folder=ROOT/identifier.replace(':','-')
        folder.mkdir()
        (folder/'flag.txt').write_text('CHECKPOINT_UNCAUGHT')
        script=folder/'main.py'
        script.write_text("from pathlib import Path\nfrom spell.runtime import Step\nfrom spell.lang.functions import SetUserAction,Pause\nStep('error-control','Error retention')\n"+BODIES[case]+"Path('finished.txt').write_text('finished')\n")
        row=dict(passed=False,case=case,mode=mode,procedure_sha256=hashlib.sha256(script.read_bytes()).hexdigest())
        session=NativeSession(folder,script,{})
        events=[]
        def drain():
            while True:
                try:event=session.events.get_nowait()
                except queue.Empty:break
                events.append(event)
                if event.get('event')=='connectionError':raise RuntimeError(event)
        def status():
            drain()
            answer=session.request('REQ_EXEC_STATUS')
            drain()
            return answer
        def wait_for(states):
            deadline=time.monotonic()+12
            observed=None
            while time.monotonic()<deadline:
                observed=status()
                if observed.get('ExecutorStatus') in states:return observed
                time.sleep(.025)
            raise TimeoutError(observed)
        try:
            session.start()
            session.pump=drain
            session.request('CMD_RUN',send=True)
            if case=='user-action-error':
                deadline=time.monotonic()+12
                while time.monotonic()<deadline:
                    row['paused']=status()
                    registered=any(e.get('message',{}).get('id')=='MSG_SET_UACTION' and e['message'].get('fields',{}).get('ActionLabel')=='Failing callback' for e in events)
                    if registered and row['paused'].get('ExecutorStatus')=='PAUSED':break
                    if row['paused'].get('ExecutorStatus') in {'ERROR','ABORTED','FINISHED'}:break
                    time.sleep(.025)
                assert registered and row['paused']['ExecutorStatus']=='PAUSED',(row['paused'],events)
                session.request('CMD_ACTION',send=True)
                deadline=time.monotonic()+5
                while not (folder/'action.txt').exists() and time.monotonic()<deadline:
                    status();time.sleep(.02)
                assert (folder/'action.txt').read_text()=='called'
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    answer=status()
                    if any('CHECKPOINT_UNCAUGHT' in str(e) for e in events):break
                    time.sleep(.02)
                assert any('CHECKPOINT_UNCAUGHT' in str(e) for e in events),events
                assert answer['ExecutorStatus']=='PAUSED',answer
                assert not (folder/'finished.txt').exists()
                session.request('CMD_RUN',send=True)
            else:
                row['error_state']=wait_for({'ERROR','ABORTED','FINISHED'})
                assert row['error_state']['ExecutorStatus']=='ERROR',row['error_state']
                assert 'CHECKPOINT_UNCAUGHT' in str(row['error_state']),row['error_state']
                assert not (folder/'finished.txt').exists()
                row['retained_state']=status()
                assert row['retained_state']['ExecutorStatus']=='ERROR'
                if mode=='DISABLED':
                    row['passed']=True
                    continue
                (folder/'flag.txt').write_text('42')
                session.request('CMD_RECOVER',send=True)
                # Recovery is asynchronous and passes ERROR -> LOADED -> PAUSED.
                # Neither the old error nor intermediate loaded status is ready.
                deadline=time.monotonic()+12
                while time.monotonic()<deadline:
                    row['recovery_state']=status()
                    if row['recovery_state'].get('ExecutorStatus') in {'PAUSED','ABORTED','FINISHED'}:break
                    time.sleep(.025)
                assert row['recovery_state']['ExecutorStatus']=='PAUSED',row['recovery_state']
                session.request('CMD_RUN',send=True)
            row['final_state']=wait_for({'FINISHED','ERROR','ABORTED'})
            assert row['final_state']['ExecutorStatus']=='FINISHED',row['final_state']
            assert (folder/'finished.txt').read_text()=='finished'
            row['passed']=True
        except Exception as error:
            row['error']=repr(error)
        finally:
            try:drain()
            except Exception as error:row['drain_error']=repr(error);row['passed']=False
            if session.log:
                session.log.flush();session.log.seek(0)
                row['log']=session.log.read()
            try:session.close()
            except Exception as error:row['cleanup_error']=repr(error);row['passed']=False
            row['events']=events
            if 'AddressSanitizer:' in row.get('log','') or 'runtime error:' in row.get('log',''):
                row['passed']=False;row['sanitizer_failure']=True
            checks[identifier]=row
            (ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
            print(json.dumps(dict(identifier=identifier,passed=row['passed'])),flush=True)
