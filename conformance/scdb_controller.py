"""Real configured native executions with independent file updates/observations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0,'/workspace')
from scdb_provenance import capture

workspace = Path('/workspace')
cases = json.loads((workspace/'cases.json').read_bytes())
checks = {}
(workspace/'runtime.json').write_text(json.dumps(capture(),indent=2))

PRELUDE = '''import sys,builtins,json,time
from pathlib import Path
assert 'spell.runtime' in sys.modules
assert hasattr(sys.modules['spell.runtime'],'SCDB') and hasattr(sys.modules['spell.runtime'],'GDB')
assert not hasattr(builtins,'SCDB') and not hasattr(builtins,'GDB')
from spell.runtime import SCDB,GDB
from spell.lang.functions import SaveDictionary,CreateDictionary,LoadDictionary,Display
from spell.lib.exception import DriverException
from spell.lib.registry import REGISTRY
notes=[]
def snapshot():
    return {'keys':list(SCDB.keys()),'values':{key:SCDB.get(key) for key in SCDB.keys()},'length':len(SCDB),'truth':bool(SCDB)}
def rejects(kind,operation):
    try:
        operation()
    except kind:
        return
    raise AssertionError('Expected '+kind.__name__)
def unchanged(operation):
    before=snapshot()
    rejected=False
    try:
        operation()
    except DriverException as error:
        rejected=True
        notes.append({'error':str(error)})
    finally:
        after=snapshot()
        notes.append({'before':before,'after':after,'rejected':rejected})
        (CASE_ROOT/'memory.json').write_text(json.dumps(notes,indent=2))
    assert rejected, 'SCDB accepted a public mutation'
    assert after==before, 'Rejected SCDB mutation changed memory'
def ask(action,content=None):
    request={'action':action,'content':content,'token':str(time.monotonic_ns())}
    temporary=CASE_ROOT/'request.tmp'
    temporary.write_text(json.dumps(request))
    temporary.replace(CASE_ROOT/'request.json')
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        answer=CASE_ROOT/('answer-'+request['token'])
        if answer.exists():
            assert answer.read_text()=='ok'
            return
        time.sleep(.01)
    raise TimeoutError('Independent database fixture did not respond')
'''


def invoke(root, example, script, log_name):
    controls=[]
    last=None
    path=root/'data/SpacecraftDB/SCDB.DB'
    with (root/log_name).open('wb') as log:
        process=subprocess.Popen(['spell-native','run','-f',str(script),'-c',example['config'],'-n','example','-d'],
            env=dict(os.environ,**example['environment']),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+45
            while process.poll() is None:
                request=root/'request.json'
                if request.exists():
                    value=json.loads(request.read_text())
                    if value['token']!=last:
                        last=value['token']
                        before=path.read_bytes() if path.exists() else None
                        if value['action']=='replace':
                            path.write_text(value['content'],encoding='utf-8')
                        elif value['action']=='remove':
                            path.unlink()
                        elif value['action']=='invalid-utf8':
                            path.write_bytes(b"SC 'partial'\nBROKEN \xff\n")
                        else:
                            raise ValueError(value)
                        after=path.read_bytes() if path.exists() else None
                        controls.append(dict(request=value,before_hex=before.hex() if before is not None else None,
                            after_hex=after.hex() if after is not None else None))
                        (root/('answer-'+last)).write_text('ok')
                if time.monotonic()>=deadline:
                    raise TimeoutError('Native SCDB case deadline exceeded')
                time.sleep(.02)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    text=(root/log_name).read_text(errors='replace')
    assert 'AddressSanitizer:' not in text and 'runtime error:' not in text
    return process.returncode,text,controls


for name,spec in cases.items():
    root=workspace/name.replace(':','-')
    row=dict(spec)
    try:
        example=json.loads(subprocess.check_output(['spell-native','init-example',str(root)],text=True))
        (root/'data/User').mkdir(exist_ok=True)
        ground=root/'data/GroundDB/GDB.DB'
        spacecraft=root/'data/SpacecraftDB/SCDB.DB'
        ground.write_text(spec['ground'],encoding='utf-8')
        spacecraft.write_text(spec['spacecraft'],encoding='utf-8')
        initial=spacecraft.read_bytes()
        script=root/'data/Procedures/main.py'
        script.write_text('from pathlib import Path\nCASE_ROOT=Path('+repr(str(root))+')\n'+PRELUDE+spec['source']+
            "\nDisplay('SCDB_READONLY_PASSED')\n",encoding='utf-8')
        code,text,controls=invoke(root,example,script,'native.log')
        row.update(returncode=code,native_log=text,controls=controls,
            file_before_sha256=hashlib.sha256(initial).hexdigest(),
            file_after_sha256=hashlib.sha256(spacecraft.read_bytes()).hexdigest() if spacecraft.exists() else None)
        if (root/'memory.json').exists():
            row['memory']=json.loads((root/'memory.json').read_bytes())
        assert code==0 and '[ STATUS  ] FINISHED' in text and 'SCDB_READONLY_PASSED' in text, 'Native assertion/execution failed'
        if not controls:
            assert spacecraft.read_bytes()==initial, 'SCDB file changed'
        if spec['fresh_source']:
            fresh=root/'data/Procedures/fresh.py'
            fresh.write_text('from pathlib import Path\nCASE_ROOT=Path('+repr(str(root))+')\n'+PRELUDE+spec['fresh_source']+
                "\nDisplay('SCDB_FRESH_READER_PASSED')\n",encoding='utf-8')
            fresh_code,fresh_text,_=invoke(root,example,fresh,'fresh.log')
            row.update(fresh_returncode=fresh_code,fresh_native_log=fresh_text)
            assert fresh_code==0 and 'SCDB_FRESH_READER_PASSED' in fresh_text
        row['passed']=True
    except Exception as error:
        row.update(passed=False,error=type(error).__name__+': '+str(error),traceback=traceback.format_exc())
        if (root/'native.log').exists():
            row.setdefault('native_log',(root/'native.log').read_text(errors='replace'))
    checks[name]=row
    (workspace/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
from scdb_checkpoint import run
checks.update(run())
(workspace/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(dict(checks=len(checks),failed={k:v.get('error') for k,v in checks.items() if not v['passed']})),flush=True)
raise SystemExit(any(not row['passed'] for row in checks.values()))
