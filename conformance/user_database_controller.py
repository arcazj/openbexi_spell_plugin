"""Run independent owned database cases with the installed native CLI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import traceback

workspace=Path('/workspace')
cases=json.loads((workspace/'cases.json').read_bytes())
example_text=json.loads((workspace/'example.json').read_bytes())
checks={}
for name,spec in cases.items():
    root=workspace/name.replace(':','-')
    try:
        example=json.loads(subprocess.check_output(['spell-native','init-example',str(root)],text=True))
        path=root/'data/User/MyData/data.IMP'
        path.parent.mkdir(parents=True)
        script=root/'data/Procedures/main.py'
        prelude='''import os
from pathlib import Path
from spell.lang.functions import CreateDictionary, LoadDictionary, SaveDictionary, Display
from spell.lang.constants import HEX, BIN
from spell.lib.adapter.utctime import TIME
from spell.lib.exception import DriverException, SyntaxException
def call(function,*args,**kwargs):
    return function(*args,HandleError=False,**kwargs)
def rejects(kind,function):
    try: function()
    except kind: return
    raise AssertionError('Expected '+kind.__name__)
path=Path(os.environ['SPELL_DATA'])/'User/MyData/data.IMP'
uri='usr://MyData/data'
'''
        script.write_text(prelude+'EXAMPLE='+repr(example_text)+'\n'+spec['source']+"\nDisplay('USER_DATABASE_PASSED')\n",encoding='utf-8')
        run=subprocess.run(['spell-native','run','-f',str(script),'-c',example['config'],'-n','example','-d'],
            env=dict(os.environ,**example['environment']),capture_output=True,timeout=40)
        (root/'native.log').write_bytes(run.stdout+run.stderr)
        assert run.returncode==0, 'Native exit '+str(run.returncode)
        assert b'[ STATUS  ] FINISHED' in run.stdout and b'USER_DATABASE_PASSED' in run.stdout
        assert b'AddressSanitizer:' not in run.stderr and b'runtime error:' not in run.stderr
        checks[name]=dict(passed=True,**spec)
    except Exception as error:
        checks[name]=dict(passed=False,error=type(error).__name__+': '+str(error),traceback=traceback.format_exc(),**spec)
    (workspace/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')

site=Path('/usr/local/lib/python3.13/site-packages')
# Load only the copied harness. Native runtime resolution remains isolated.
import sys
sys.path.insert(0,str(workspace))
from user_database_prompts import run as run_prompts
(workspace/'prompts.json').write_text(json.dumps(run_prompts(workspace),indent=2)+'\n')
paths=['spell/lib/adapter/databases/dbfile.py','spell/utils/vimport.py','spell/lang/helpers/filehelper.py']
paths.extend(str(path.relative_to(site)) for path in (site/'spell_native/bin').iterdir() if path.is_file())
installed={name:hashlib.sha256((site/name).read_bytes()).hexdigest() for name in paths}
for absolute in ('/opt/host/native.py','/bridge/spell-host-ipc'):
    installed[absolute]=hashlib.sha256(Path(absolute).read_bytes()).hexdigest()
manifest=Path('/opt/user-database-patch/manifest.json')
report=dict(installed=installed,manifest=json.loads(manifest.read_bytes()) if manifest.exists() else {})
(workspace/'runtime.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(checks=len(checks),failed={k:v.get('error') for k,v in checks.items() if not v['passed']})),flush=True)
raise SystemExit(any(not row['passed'] for row in checks.values()))
