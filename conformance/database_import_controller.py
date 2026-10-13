"""Execute real configured database fixtures with the installed native CLI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import traceback

workspace = Path('/workspace')
cases = json.loads((workspace / 'cases.json').read_bytes())
checks = {}


def invoke(root, example, script):
    result = subprocess.run(['spell-native','run','-f',str(script),'-c',example['config'],'-n','example','-d'],
        env=dict(os.environ, **example['environment']), capture_output=True, timeout=40)
    (root / 'native.log').write_bytes(result.stdout + result.stderr)
    assert b'AddressSanitizer:' not in result.stderr and b'runtime error:' not in result.stderr
    return result


for name, spec in cases.items():
    root = workspace / name.replace(':','-')
    try:
        example = json.loads(subprocess.check_output(['spell-native','init-example',str(root)],text=True))
        (root / 'data/GroundDB/GDB.DB').write_text(spec['ground'],encoding='utf-8')
        (root / 'data/SpacecraftDB/SCDB.DB').write_text(spec['spacecraft'],encoding='utf-8')
        script = root / 'data/Procedures/main.py'
        # The established port exposes interpreter-local runtime bindings through
        # explicit imports. Prove startup populated them before this prelude;
        # neither the procedure nor its import loads or replaces a database.
        code = '''import sys, builtins
assert 'spell.runtime' in sys.modules
assert hasattr(sys.modules['spell.runtime'], 'GDB')
assert hasattr(sys.modules['spell.runtime'], 'SCDB')
assert not hasattr(builtins, 'GDB') and not hasattr(builtins, 'SCDB')
from spell.runtime import GDB, SCDB
from spell.lang.functions import Display
from spell.lib.exception import DriverException
def rejects(kind, action):
    try:
        action()
    except kind:
        return
    raise AssertionError('Expected '+kind.__name__)
''' + spec['source'] + "\nDisplay('CONFIGURED_DATABASE_PASSED')\n"
        script.write_text(code,encoding='utf-8')
        result = invoke(root, example, script)
        assert result.returncode == 0, 'Native startup/execution failed: ' + str(result.returncode)
        assert b'[ STATUS  ] FINISHED' in result.stdout
        assert b'CONFIGURED_DATABASE_PASSED' in result.stdout
        checks[name] = dict(passed=True, **spec)
    except Exception as error:
        checks[name] = dict(passed=False, error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc(), **spec)
    (workspace / 'checks.json').write_text(json.dumps(checks,indent=2)+'\n')

site = Path('/usr/local/lib/python3.13/site-packages')
manifest = Path('/opt/database-import-patch/manifest.json')
manifests = json.loads(manifest.read_bytes()) if manifest.exists() else {}
installed = {}
for relative in ('spell/utils/vimport.py', 'spell/lib/adapter/databases/dbfile.py'):
    installed[relative] = hashlib.sha256((site / relative).read_bytes()).hexdigest()
    if relative in manifests:
        assert installed[relative] == manifests[relative]['sha256']
for path in (site / 'spell_native/bin').iterdir():
    if path.is_file(): installed[str(path.relative_to(site))] = hashlib.sha256(path.read_bytes()).hexdigest()
(workspace / 'runtime.json').write_text(json.dumps(dict(installed=installed, manifests=manifests),indent=2)+'\n')
print(json.dumps(dict(checks=len(checks), failed={k:v.get('error') for k,v in checks.items() if not v['passed']})),flush=True)
raise SystemExit(any(not row['passed'] for row in checks.values()))
