"""Actual native CreateDictionary retry/name and abort prompts."""
import json
from pathlib import Path
import queue
import sys
import time
import traceback

sys.path.insert(0,'/opt/host')
from native import NativeSession


def run(workspace):
    checks={}
    for mode in ('rename','abort'):
        root=workspace/('prompt-'+mode)
        root.mkdir()
        script=root/'main.py'
        script.write_text('''import os
from pathlib import Path
from spell.lang.functions import CreateDictionary, SaveDictionary, LoadDictionary
from spell.lang.constants import REPEAT, ABORT
path=Path(os.environ['SPELL_DATA'])/'User/MyData'
path.mkdir(parents=True)
(path/'existing.IMP').write_bytes(b'SAVED 42\\n')
db=CreateDictionary('usr://MyData/existing',OnFailure=REPEAT|ABORT,PromptFailure=True)
assert db.id()=='renamed.IMP'
db['KEY']=7
assert SaveDictionary(db,HandleError=False) is True
assert LoadDictionary('usr://MyData/renamed',HandleError=False)['KEY']==7
assert (path/'existing.IMP').read_bytes()==b'SAVED 42\\n'
Path('completed.txt').write_text('renamed')
''',encoding='utf-8')
        session=NativeSession(root,script,{})
        events,prompts,pending=[],[],[]
        record=dict(passed=False,mode=mode,prompts=prompts,events=events)
        def drain():
            while True:
                try: event=session.events.get_nowait()
                except queue.Empty: return
                events.append(event)
                if event.get('event')=='connectionError': raise RuntimeError(event)
                message=event.get('message',{})
                if message.get('id')=='MSG_PROMPT': pending.append(message)
        try:
            session.start()
            session.pump=drain
            session.request('CMD_RUN',send=True)
            deadline=time.monotonic()+35
            while time.monotonic()<deadline:
                drain()
                while pending:
                    message=pending.pop(0)
                    fields=message['fields']
                    codes=fields.get('ExpectedValues','').split('\x04')
                    if not prompts:
                        assert set(codes)=={'R','A'},fields
                        answer=str(codes.index('R' if mode=='rename' else 'A'))
                    else:
                        assert mode=='rename' and len(prompts)==1,fields
                        assert 'Enter new database name' in json.dumps(fields),fields
                        answer='MyData/renamed'
                    prompts.append(dict(fields=fields,answer=answer))
                    session.request('MSG_ANSWER',{'ReturnValue':answer},send=True)
                status=session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
                if status in ('FINISHED','ERROR','ABORTED'): break
                time.sleep(.01)
            else: raise TimeoutError('Native database prompt timed out')
            drain()
            record['status']=status
            data=Path(session.directory.name)/'session/data/User/MyData'
            record['files']={p.name:p.read_text(encoding='utf-8') for p in data.iterdir() if p.is_file()}
            assert record['files']['existing.IMP']=='SAVED 42\n'
            if mode=='rename':
                assert status=='FINISHED' and len(prompts)==2
                assert (root/'completed.txt').read_text()=='renamed'
                assert record['files']['renamed.IMP']=='KEY\t7\n'
            else:
                assert status=='ABORTED' and len(prompts)==1,status
                assert not (root/'completed.txt').exists() and set(record['files'])=={'existing.IMP'}
            record['passed']=True
        except Exception as error:
            record.update(error=type(error).__name__+': '+str(error),traceback=traceback.format_exc())
        finally:
            if session.log:
                session.log.flush()
                session.log.seek(0)
                (root/'native.log').write_text(session.log.read(),encoding='utf-8')
            try: session.close()
            except Exception as error: record.update(passed=False,cleanup_error=str(error))
        checks['prompt-'+mode]=record
    return checks
