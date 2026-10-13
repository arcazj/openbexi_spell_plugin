"""Bounded actual native controls for exception frames after checkpoint restore."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path('/workspace')
sys.path.insert(0, str(ROOT))
options = json.loads((ROOT/'input.json').read_bytes())
CASES = {
    'direct-valueerror': """try:
    int('plain original error')
except ValueError:
    events.append('caught')
""",
    'lambda-valueerror': """operation=lambda:int('plain original error')
try:
    operation()
except ValueError:
    events.append('caught')
""",
    'named-valueerror': """def operation():
    return int('plain original error')
try:
    operation()
except ValueError:
    events.append('caught')
""",
    'lambda-keyerror': """operation=lambda:{}['missing']
try:
    operation()
except KeyError:
    events.append('caught')
""",
    'lambda-success': """operation=lambda:42
assert operation()==42
events.append('caught')
""",
    'lambda-original-driver': """from spell.runtime import SCDB
from spell.lib.exception import DriverException
operation=lambda:SCDB['missing']
try:
    operation()
except DriverException:
    events.append('caught')
""",
    'nested-unwind': """def deepest():
    raise ValueError('nested')
def middle():
    deepest()
try:
    middle()
except ValueError:
    events.append('caught')
""",
    'finally-unwind': """def operation():
    try:
        int('nested')
    finally:
        events.append('finally')
try:
    operation()
except ValueError:
    assert events.pop()=='finally'
    events.append('caught')
""",
    'replace-error': """def operation():
    try:
        int('nested')
    except ValueError:
        raise KeyError('replacement')
try:
    operation()
except KeyError:
    events.append('caught')
""",
    'recursive-unwind': """def operation(depth):
    if depth:
        return operation(depth-1)
    raise ValueError('recursive')
try:
    operation(3)
except ValueError:
    events.append('caught')
""",
    'repeated-catch': """def operation():
    raise ValueError('repeat')
for attempt in range(3):
    try:
        operation()
    except ValueError:
        events.append(attempt)
assert events==[0,1,2]
events.clear()
events.append('caught')
""",
    'lambda-scdb-write': """from spell.runtime import SCDB
from spell.lib.exception import DriverException
operation=lambda:SCDB.set('SC','changed')
try:
    operation()
except DriverException:
    events.append('caught')
""",
}
if Path('/opt/checkpoint-error-patch').exists():
    from checkpoint_error_provenance import capture
elif Path('/opt/scdb-patch').exists():
    from scdb_provenance import capture
else:
    from installed_provenance import capture
(ROOT/'runtime.json').write_text(json.dumps(capture(),indent=2))
checks={}
for mode in options['modes']:
    for case in options['cases']:
        for execution in options['executions']:
            identifier=mode+':'+case+':'+execution
            folder=ROOT/identifier.replace(':','-')
            folder.mkdir()
            row=dict(mode=mode,case=case,execution=execution,passed=False)
            process=None
            prefix=b''
            try:
                example=json.loads(subprocess.check_output(['spell-native','init-example',str(folder/'example')],text=True))
                context=folder/'example/config/contexts/context_example.xml'
                tree=ET.parse(context)
                tree.find("./executor/property[@name='SaveStateMode']").text=mode
                tree.write(context,encoding='utf-8')
                output=folder/'result.json'
                effect=folder/'effect.txt'
                script=folder/'procedure.py'
                script.write_text('from spell.runtime import Step\nfrom pathlib import Path\nimport json\n'
                    +f'Path({str(effect)!r}).write_text("module executed")\n'
                    +'events=[]\ndef nested():\n    Step("checkpoint-control","Original error control")\n'
                    +'    print("CHECKPOINT_ERROR_READY",flush=True)\n    assert input()=="continue"\n'
                    +''.join('    '+line+'\n' for line in CASES[case].splitlines())
                    +'    assert events==["caught"]\n'
                    +f'    Path({str(output)!r}).write_text(json.dumps(events))\n'
                    +'nested()\n',encoding='utf-8')
                row['procedure_sha256']=hashlib.sha256(script.read_bytes()).hexdigest()
                command=['spell-native','run','-f',str(script),'-c',example['config'],'-n','example']
                environment=dict(os.environ,**example['environment'])
                process=subprocess.Popen(command+['-w'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,env=environment)
                if execution=='resume':
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdout,selectors.EVENT_READ)
                        deadline=time.monotonic()+20
                        while b'CHECKPOINT_ERROR_READY' not in prefix and time.monotonic()<deadline:
                            if selector.select(timeout=max(0,deadline-time.monotonic())):
                                chunk=os.read(process.stdout.fileno(),65536)
                                if not chunk:break
                                prefix+=chunk
                    assert b'CHECKPOINT_ERROR_READY' in prefix,prefix.decode(errors='replace')
                    checkpoint,=list((Path(example['environment']['SPELL_DATA'])/'OutputFiles/Warmstart').glob('*.wsp'))
                    row['checkpoint_sha256']=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
                    effect.write_text('preserve after crash')
                    process.kill()
                    stdout,stderr=process.communicate(timeout=10)
                    row.update(capture_returncode=process.returncode,capture_log=(prefix+stdout+stderr).decode(errors='replace'))
                    assert process.returncode==-9
                    process=subprocess.Popen(command+['-r',checkpoint.stem],stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment)
                try:
                    stdout,stderr=process.communicate(b'continue\n',timeout=15)
                    row.update(returncode=process.returncode,log=(stdout+stderr).decode(errors='replace'))
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout,stderr=process.communicate(timeout=10)
                    row.update(timed_out=True,returncode=process.returncode,log=(stdout+stderr).decode(errors='replace'))
                assert row['returncode']==0,row['log']
                assert json.loads(output.read_bytes())==['caught']
                assert effect.read_text()==('preserve after crash' if execution=='resume' else 'module executed')
                assert 'AddressSanitizer:' not in row['log'] and 'runtime error:' not in row['log']
                row['passed']=True
            except Exception as error:
                row['error']=repr(error)
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    stdout,stderr=process.communicate(timeout=10)
                    row['cleanup_log']=(prefix+stdout+stderr).decode(errors='replace')
            checks[identifier]=row
            (ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
            print(json.dumps(dict(identifier=identifier,passed=row['passed'])),flush=True)
