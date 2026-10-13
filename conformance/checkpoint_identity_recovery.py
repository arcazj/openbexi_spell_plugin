"""Real context checkpoint identity, independent instances and recovery rejection."""
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
import io
import marshal
import zlib


def metadata(path):
    raw=path.read_bytes()
    stream=io.BytesIO(raw)
    assert stream.readline().startswith(b'OPENBEXI_SPELL_WS/1|CPython/')
    sequence,kind,size,crc=stream.readline().decode().strip().split('\x01')
    encoded=stream.read(int(size))
    assert int(sequence)==1 and zlib.crc32(encoded)==int(crc)
    value=marshal.loads(encoded)
    assert isinstance(value,dict) and value['format']=='SPELL-continuation/2'
    return dict(filename=path.name,sha256=hashlib.sha256(raw).hexdigest(),metadata=value)

SOURCE="""from pathlib import Path
import json
from spell.runtime import ARGS,Step
from spell.lang.functions import Prompt
from spell.lang.constants import ALPHA
value=ARGS['value']
effect=Path('effects-'+str(value)+'.txt')
effect.write_text((effect.read_text() if effect.exists() else '')+'module executed\\n')
def nested(counter):
    saved=[counter,'nested']
    Step('READY','Independent instance state')
    answer=Prompt('CHECKPOINT_IDENTITY_READY',Type=ALPHA)
    assert answer=='continue'
    Path('result-'+str(saved[0])+'.json').write_text(json.dumps(saved))
nested(value)
"""
checks={}
for mode in options['modes']:
    os.environ['CHECKPOINT_MODE']=mode
    for case in options['cases']:
        identifier=mode+':'+case
        folder=ROOT/identifier.replace(':','-')
        folder.mkdir()
        script=folder/'main.py'
        script.write_text(SOURCE)
        source_hash=hashlib.sha256(script.read_bytes()).hexdigest()
        row=dict(passed=False,case=case,mode=mode,procedure_sha256=source_hash)
        session=NativeSession(folder,script,{'value':11})
        events=[];extra_open=False
        def drain():
            while True:
                try:event=session.events.get_nowait()
                except queue.Empty:break
                events.append(event)
                if event.get('event')=='connectionError':raise RuntimeError(event)
        def request(identifier,instance='main#1',fields=None,context=False,send=False):
            return session.context.exchange(identifier,'CTX' if context else instance,
                dict(fields or {},ProcId=instance),send=send,pump=drain)
        def status(instance='main#1'):
            drain();answer=request('REQ_EXEC_STATUS',instance);drain();return answer
        def wait_for(states,instance='main#1'):
            deadline=time.monotonic()+12
            while time.monotonic()<deadline:
                answer=status(instance)
                if answer.get('ExecutorStatus') in states:return answer
                time.sleep(.025)
            raise TimeoutError(answer)
        def files(instance):
            warm=Path(session.directory.name)/'session/data/OutputFiles/Warmstart'
            return list(warm.glob('*_Executor_'+instance+'.wsp'))
        def recorded(instance):
            paths=files(instance)
            assert len(paths)==1,paths
            path=paths[0]
            record=metadata(path)
            assert record['metadata']['source_sha256']==source_hash,record
            (folder/record['filename']).write_bytes(path.read_bytes())
            return path,record
        def complete(instance,value):
            request('MSG_ANSWER',instance,{'ReturnValue':'continue'},send=True)
            final=wait_for({'FINISHED','ERROR','ABORTED'},instance)
            assert final['ExecutorStatus']=='FINISHED',final
            assert json.loads((folder/('result-'+str(value)+'.json')).read_bytes())==[value,'nested']
            assert (folder/('effects-'+str(value)+'.txt')).read_text()=='module executed\n'
            return final
        try:
            session.start();session.pump=drain
            assert not (folder/'main#1').exists(), 'No source-path alias is allowed'
            request('CMD_RUN',send=True)
            first=wait_for({'PROMPT','ERROR','ABORTED'})
            assert first['ExecutorStatus']=='PROMPT',first
            checkpoint,saved=recorded('main#1')
            row['checkpoint']=saved
            if case=='normal':
                row['final']=complete('main#1',11)
            elif case=='two-instances':
                row['open_second']=request('REQ_OPEN_EXEC','main#2',{'GuiMode':'CONTROL',
                    'Arguments':"{'value':22}",'OpenMode':'{Automatic:True,Visible:True,Blocking:False}'},context=True)
                extra_open=True
                second=wait_for({'PAUSED','ERROR','ABORTED'},'main#2')
                assert second['ExecutorStatus']=='PAUSED',second
                request('CMD_RUN','main#2',send=True)
                second=wait_for({'PROMPT','ERROR','ABORTED'},'main#2')
                assert second['ExecutorStatus']=='PROMPT',second
                _,other=recorded('main#2');row['second_checkpoint']=other
                assert saved['filename']!=other['filename'] and saved['sha256']!=other['sha256']
                assert saved['metadata']['source_sha256']==other['metadata']['source_sha256']
                row['second_final']=complete('main#2',22)
                assert status()['ExecutorStatus']=='PROMPT'
                row['first_final']=complete('main#1',11)
            else:
                assert case in ('kill-resume','changed-source','missing-wsp','empty-wsp',
                    'corrupt-wsp','missing-asrun','empty-asrun','invalid-path','partial-stem')
                row['kill']=request('REQ_KILL_EXEC',context=True)
                session.opened=False
                assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==saved['sha256']
                matches=list((Path(session.directory.name)/'session/data').rglob(checkpoint.stem+'.ASRUN'))
                assert len(matches)==1,matches
                asrun=matches[0]
                expected_reason=None
                requested=checkpoint.stem
                if case=='changed-source':
                    script.write_text(SOURCE+'\n# changed after checkpoint\n')
                    expected_reason='source/runtime identity mismatch'
                elif case=='missing-wsp':checkpoint.unlink();expected_reason='WSP data file missing'
                elif case=='empty-wsp':checkpoint.write_bytes(b'');expected_reason='WSP data file has zero bytes'
                elif case=='corrupt-wsp':
                    damaged=bytearray(checkpoint.read_bytes())
                    # Corrupt the first metadata payload while preserving its header.
                    offset=damaged.index(10,damaged.index(10)+1)+1
                    damaged[offset]^=1
                    checkpoint.write_bytes(damaged)
                    expected_reason='Record checksum differs'
                elif case=='missing-asrun':asrun.unlink();expected_reason='ASRUN file missing'
                elif case=='empty-asrun':asrun.write_bytes(b'');expected_reason='ASRUN file has zero bytes'
                elif case=='partial-stem':requested=checkpoint.stem[1:];expected_reason='WSP data file missing'
                preserved=checkpoint.read_bytes() if checkpoint.exists() else None
                if case=='invalid-path':
                    row['rejected_names']={}
                    for requested in ('../'+checkpoint.stem, '..\\'+checkpoint.stem, '/'+checkpoint.stem,
                            '.', '..', ''):
                        try:request('REQ_RECOVER_EXEC',fields={'FileName':requested},context=True)
                        except RuntimeError as error:failure=str(error)
                        else:raise AssertionError('Invalid recovery basename was accepted: '+repr(requested))
                        assert 'Invalid recovery basename' in failure,failure
                        row['rejected_names'][requested]=failure
                else:
                    reopen_event_start=len(events)
                    try:
                        row['reopen']=request('REQ_RECOVER_EXEC',fields={'FileName':requested},context=True)
                        session.opened=True
                    except RuntimeError as error:
                        row['reopen_error']=str(error)
                        assert expected_reason and expected_reason in str(error),str(error)
                    else:
                        if expected_reason:
                            assert case in ('changed-source','corrupt-wsp'), 'Preflight should reject before opening'
                            deadline=time.monotonic()+12
                            rejection=None
                            while time.monotonic()<deadline:
                                row['rejection_status']=status()
                                for event in events[reopen_event_start:]:
                                    message=event.get('message',{})
                                    fields=message.get('fields',{})
                                    if (message.get('id')=='MSG_ERROR' and fields.get('ProcId')=='main#1'
                                            and expected_reason in str(fields)):
                                        rejection=message
                                if rejection:break
                                time.sleep(.025)
                            assert rejection,(row['rejection_status'],events[reopen_event_start:])
                            assert rejection['fields']['ExecutorStatus']=='ERROR'
                            assert rejection['fields']['FatalError']=='True'
                            row['rejection_message']=rejection
                        else:
                            state=wait_for({'PAUSED','PROMPT','ERROR','ABORTED'})
                            if state['ExecutorStatus']=='PAUSED':
                                request('CMD_RUN',send=True)
                                state=wait_for({'PROMPT','ERROR','ABORTED'})
                            row['resume_state']=state
                            assert state['ExecutorStatus']=='PROMPT',state
                            row['resumed_checkpoints']=[metadata(p) for p in files('main#1')]
                            assert row['resumed_checkpoints']
                            assert all(p['metadata']['source_sha256']==source_hash for p in row['resumed_checkpoints'])
                            row['final']=complete('main#1',11)
                if expected_reason or case=='invalid-path':
                    assert not (folder/'result-11.json').exists()
                    assert (folder/'effects-11.txt').read_text()=='module executed\n'
                    assert (checkpoint.read_bytes() if checkpoint.exists() else None)==preserved
                else:
                    row['original_checkpoint_unchanged']=(checkpoint.read_bytes() if checkpoint.exists() else None)==preserved
            row['passed']=True
        except Exception as error:row['error']=repr(error)
        finally:
            try:drain()
            except Exception as error:row['drain_error']=repr(error);row['passed']=False
            if session.log:
                session.log.flush();session.log.seek(0);row['log']=session.log.read()
            if extra_open:
                try:request('REQ_CLOSE_EXEC','main#2',context=True)
                except Exception as error:row['extra_cleanup_error']=repr(error);row['passed']=False
            try:session.close()
            except Exception as error:row['cleanup_error']=repr(error);row['passed']=False
            row['events']=events
            if 'AddressSanitizer:' in row.get('log','') or 'runtime error:' in row.get('log',''):
                row['passed']=False;row['sanitizer_failure']=True
            checks[identifier]=row
            (ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
            print(json.dumps(dict(identifier=identifier,passed=row['passed'])),flush=True)
