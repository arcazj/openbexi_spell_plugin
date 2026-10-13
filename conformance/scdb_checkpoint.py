"""Actual native kill/resume with SCDB aliases and detached nested values."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import time
import xml.etree.ElementTree as ET


def run():
    checks={}
    for mode in ('ON_LINE','ON_STEP'):
        identifier='checkpoint:'+mode.lower()
        row=dict(dimension='recovery',contracts=[],mode=mode,
            oracle='Native executor checkpoint is killed and restored without rerunning module effects; saved SCDB aliases retain shared identity/read-only policy and detached nested data remains independent.')
        folder=Path('/workspace/checkpoint-'+mode.lower())
        folder.mkdir()
        process=None
        prefix=b''
        try:
            example=json.loads(subprocess.check_output(['spell-native','init-example',str(folder/'example')],text=True))
            context=folder/'example/config/contexts/context_example.xml'
            tree=ET.parse(context)
            tree.find("./executor/property[@name='SaveStateMode']").text=mode
            tree.write(context,encoding='utf-8')
            spacecraft=Path(example['environment']['SPELL_DATA'])/'SpacecraftDB/SCDB.DB'
            spacecraft.write_text("SC 'Checkpoint spacecraft'\nNESTED {'items':[1,{'flag':False}]}\n")
            original_database=spacecraft.read_bytes()
            effect=folder/'effect.txt'
            result=folder/'restored.json'
            script=folder/'procedure.py'
            script.write_text(f'''from spell.runtime import SCDB,Step
from spell.lang.functions import SaveDictionary
from spell.lib.exception import DriverException
from pathlib import Path
import json
Path({str(effect)!r}).write_text('module executed')
alias=SCDB
saved={{'db':SCDB,'nested':SCDB['NESTED']}}
saved['nested']['items'].append('local only')
def nested(db,state):
    Step('scdb-checkpoint','Preserve read-only database aliases')
    print('SCDB_CHECKPOINT_READY',flush=True)
    assert input()=='continue'
    from spell.runtime import SCDB as initialized
    assert db is alias and db is state['db']
    assert db is initialized and type(db) is type(initialized)
    assert db['SC']=='Checkpoint spacecraft'
    assert db['NESTED']=={{'items':[1,{{'flag':False}}]}}
    assert state['nested']=={{'items':[1,{{'flag':False}},'local only']}}
    for method,args in (('__setitem__',('SC','changed')),('__delitem__',('SC',)),
                        ('set',('NEW',1)),('create',()),('commit',())):
        try:
            getattr(db,method)(*args)
        except DriverException:
            pass
        else:
            raise AssertionError('Restored SCDB accepted a write')
    try:
        SaveDictionary(db,HandleError=False)
    except DriverException:
        pass
    else:
        raise AssertionError('Restored SCDB accepted SaveDictionary')
    value=db['NESTED']
    value['items'].append('another local change')
    assert db['NESTED']=={{'items':[1,{{'flag':False}}]}}
    Path({str(result)!r}).write_text(json.dumps({{'restored':True,'shared_saved_alias':True,
        'alias_is_new_runtime_binding':db is initialized,'readonly_type':type(db).__name__}}))
nested(alias,saved)
''',encoding='utf-8')
            command=['spell-native','run','-f',str(script),'-c',example['config'],'-n','example']
            environment=dict(os.environ,**example['environment'])
            process=subprocess.Popen(command+['-w'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,env=environment)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                deadline=time.monotonic()+30
                while b'SCDB_CHECKPOINT_READY' not in prefix and time.monotonic()<deadline:
                    if selector.select(timeout=max(0,deadline-time.monotonic())):
                        chunk=os.read(process.stdout.fileno(),65536)
                        if not chunk:break
                        prefix+=chunk
            assert b'SCDB_CHECKPOINT_READY' in prefix, prefix.decode(errors='replace')
            checkpoint,=list((Path(example['environment']['SPELL_DATA'])/'OutputFiles/Warmstart').glob('*.wsp'))
            original=checkpoint.read_bytes()
            effect.write_text('preserve after crash')
            process.kill()
            stdout,stderr=process.communicate(timeout=10)
            row.update(capture_returncode=process.returncode,capture_log=(prefix+stdout+stderr).decode(errors='replace'))
            assert process.returncode==-9
            restored=subprocess.run(command+['-r',checkpoint.stem],input='continue\n',
                capture_output=True,text=True,timeout=30,env=environment)
            row.update(resume_returncode=restored.returncode,resume_log=restored.stdout+restored.stderr,
                checkpoint_sha256=hashlib.sha256(original).hexdigest(),procedure_sha256=hashlib.sha256(script.read_bytes()).hexdigest())
            assert restored.returncode==0, row['resume_log']
            row['result']=json.loads(result.read_bytes())
            assert row['result']['restored'] and row['result']['shared_saved_alias']
            assert row['result']['alias_is_new_runtime_binding']
            assert row['result']['readonly_type']=='ReadOnlyDatabase'
            assert checkpoint.read_bytes()==original and spacecraft.read_bytes()==original_database
            assert effect.read_text()=='preserve after crash'
            assert 'AddressSanitizer:' not in row['resume_log'] and 'runtime error:' not in row['resume_log']
            row['passed']=True
        except Exception as error:
            row.update(passed=False,error=repr(error))
            if isinstance(error,subprocess.TimeoutExpired):
                row['timeout_stdout']=(error.stdout or b'').decode(errors='replace')
                row['timeout_stderr']=(error.stderr or b'').decode(errors='replace')
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                stdout,stderr=process.communicate(timeout=10)
                row['capture_log']=(prefix+stdout+stderr).decode(errors='replace')
        checks[identifier]=row
    return checks
