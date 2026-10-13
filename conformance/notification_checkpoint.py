"""Kill/resume real installed executor checkpoints containing Notify tokens."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import time
import xml.etree.ElementTree as ET


def run():
    checks = {}
    for mode in ('ON_LINE', 'ON_STEP'):
        identifier = 'modifier:checkpoint-' + mode.lower()
        row = dict(dimension='recovery', contracts=[], mode=mode)
        folder = Path('/workspace/checkpoint-' + mode.lower())
        folder.mkdir()
        process = None
        try:
            example = json.loads(subprocess.check_output(['spell-native','init-example',str(folder/'example')],text=True))
            context = folder/'example/config/contexts/context_example.xml'
            tree = ET.parse(context)
            tree.find("./executor/property[@name='SaveStateMode']").text = mode
            tree.write(context,encoding='utf-8')
            effect = folder/'effect.txt'
            result = folder/'restored.json'
            script = folder/'procedure.py'
            script.write_text(f'''from spell.lang.functions import Notify
from spell.lang.modifiers import Notify as Modifier
from spell.lang.constants import ITEM_SUCCESS
from spell.runtime import Step
from pathlib import Path
import json
Path({str(effect)!r}).write_text('module executed')
saved = {{Notify: False}}
alias = Notify
def nested(settings, operation):
    Step('notify-checkpoint', 'Preserve callable modifier')
    print('NOTIFY_CHECKPOINT_READY', flush=True)
    assert input() == 'continue'
    assert operation is Notify and callable(operation)
    assert next(iter(settings)) is Notify and settings['Notify'] is False
    assert alias is Modifier and callable(alias)
    operation('CheckpointNotify', 'restored', ITEM_SUCCESS)
    Path({str(result)!r}).write_text(json.dumps({{'restored': True, 'identity': True}}))
nested(saved, Notify)
''',encoding='utf-8')
            command = ['spell-native','run','-f',str(script),'-c',example['config'],'-n','example']
            environment = dict(os.environ, **example['environment'])
            process = subprocess.Popen(command+['-w'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,env=environment)
            prefix = b''
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                deadline = time.monotonic()+30
                while b'NOTIFY_CHECKPOINT_READY' not in prefix and time.monotonic()<deadline:
                    if selector.select(timeout=max(0,deadline-time.monotonic())):
                        chunk = os.read(process.stdout.fileno(),65536)
                        if not chunk:
                            break
                        prefix += chunk
            assert b'NOTIFY_CHECKPOINT_READY' in prefix, prefix.decode(errors='replace')
            checkpoints = list((Path(example['environment']['SPELL_DATA'])/'OutputFiles/Warmstart').glob('*.wsp'))
            checkpoint, = checkpoints
            original = checkpoint.read_bytes()
            effect.write_text('preserve after crash')
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
            row['capture_returncode'] = process.returncode
            row['capture_log'] = (prefix+stdout+stderr).decode(errors='replace')
            assert process.returncode == -9
            restored = subprocess.run(command+['-r',checkpoint.stem],input='continue\n',
                capture_output=True,text=True,timeout=30,env=environment)
            row['resume_returncode'] = restored.returncode
            row['resume_log'] = restored.stdout+restored.stderr
            row['checkpoint_sha256'] = hashlib.sha256(original).hexdigest()
            row['procedure_sha256'] = hashlib.sha256(script.read_bytes()).hexdigest()
            assert restored.returncode == 0, row['resume_log']
            assert json.loads(result.read_text()) == dict(restored=True,identity=True)
            assert checkpoint.read_bytes() == original
            assert effect.read_text() == 'preserve after crash'
            assert 'AddressSanitizer:' not in row['resume_log'] and 'runtime error:' not in row['resume_log']
            row['passed'] = True
        except Exception as error:
            row.update(passed=False,error=repr(error))
            if isinstance(error, subprocess.TimeoutExpired):
                row['timeout_stdout'] = (error.stdout or b'').decode(errors='replace')
                row['timeout_stderr'] = (error.stderr or b'').decode(errors='replace')
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                stdout, stderr = process.communicate(timeout=10)
                row['capture_log'] = (prefix+stdout+stderr).decode(errors='replace')
        checks[identifier] = row
        Path('notification-checkpoints.json').write_text(json.dumps(dict(checks=checks),indent=2))
    return checks
