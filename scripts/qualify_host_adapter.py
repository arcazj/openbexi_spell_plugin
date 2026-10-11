"""Independent DAP client: exercise the installed native host image from Windows."""
import argparse
from collections import deque
import hashlib
import io
import json
from pathlib import Path
import queue
import subprocess
import tarfile
import tempfile
import threading
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'openbexi-spell-host:0.3.0'
EVIDENCE = ROOT / '.qualification/v0.3/adapter'


class Client:
    def __init__(self, project):
        self.project = project
        self.name = 'openbexi-host-test-' + uuid.uuid4().hex
        self.sequence = 0
        self.events = deque()
        self.messages = queue.Queue()
        self.transcript = []
        self.errors = tempfile.TemporaryFile()
        self.process = None

    def start(self):
        subprocess.run(['docker', 'create', '--init', '-i',
            '--name', self.name, '--network', 'none', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--pids-limit', '256',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m', IMAGE],
            capture_output=True, check=True, timeout=20)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as tar:
            for path in sorted(self.project.rglob('*')):
                if not path.is_file():
                    continue
                content = path.read_bytes()
                info = tarfile.TarInfo(path.relative_to(self.project).as_posix())
                info.size = len(content)
                info.mode = 0o644
                info.uid = info.gid = 10003
                tar.addfile(info, io.BytesIO(content))
        subprocess.run(['docker', 'cp', '-a', '-', self.name + ':/workspace'],
                       input=archive.getvalue(), capture_output=True, check=True, timeout=20)
        self.process = subprocess.Popen(['docker', 'start', '-ai', self.name],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.errors)
        self.thread = threading.Thread(target=self.read)
        self.thread.start()

    def read(self):
        try:
            while True:
                length = None
                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        raise EOFError('Adapter ended')
                    if line == b'\r\n':
                        break
                    key, value = line.decode('ascii').split(':', 1)
                    if key.lower() == 'content-length':
                        length = int(value)
                message = json.loads(self.process.stdout.read(length))
                self.transcript.append(message)
                self.messages.put(message)
        except Exception as error:
            self.messages.put(error)

    def send(self, command, **arguments):
        self.sequence += 1
        message = {'seq': self.sequence, 'type': 'request', 'command': command, 'arguments': arguments}
        self.transcript.append(message)
        data = json.dumps(message).encode()
        self.process.stdin.write(f'Content-Length: {len(data)}\r\n\r\n'.encode() + data)
        self.process.stdin.flush()
        return self.sequence

    def next(self, timeout=30):
        message = self.messages.get(timeout=timeout)
        if isinstance(message, Exception):
            self.errors.seek(0)
            raise AssertionError(str(message) + '\n' + self.errors.read().decode(errors='replace'))
        return message

    def request(self, command, *, success=True, **arguments):
        sequence = self.send(command, **arguments)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            message = self.next(deadline - time.monotonic())
            if message.get('type') == 'response' and message['request_seq'] == sequence:
                assert message['success'] == success, message
                return message.get('body', {})
            self.events.append(message)
        raise AssertionError('Request timed out: ' + command)

    def event(self, event):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            for message in tuple(self.events):
                if message.get('event') == event:
                    self.events.remove(message)
                    return message.get('body', {})
            self.events.append(self.next(deadline - time.monotonic()))
        raise AssertionError('Event timed out: ' + event)

    def launch(self, script, **extra):
        self.start()
        self.request('initialize', adapterID='spell', linesStartAt1=True, pathFormat='path')
        self.request('launch', project=str(self.project), program=str(self.project / script), **extra)
        self.event('initialized')

    def read_file(self, relative):
        result = subprocess.run(['docker', 'cp', self.name + ':/workspace/' + relative, '-'],
                                capture_output=True, check=True, timeout=10)
        with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tar:
            return tar.extractfile(tar.getmembers()[0]).read().decode('utf-8')

    def close(self, label):
        try:
            if self.process is not None and self.process.poll() is None:
                self.request('disconnect', terminateDebuggee=True)
                self.process.stdin.close()
                assert self.process.wait(timeout=20) == 0
        finally:
            subprocess.run(['docker', 'rm', '-f', self.name], capture_output=True, timeout=20)
            if self.process is not None and self.process.poll() is None:
                self.process.kill()
            if self.process is not None:
                self.process.wait(timeout=5)
                self.thread.join(timeout=5)
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            (EVIDENCE / (label + '.json')).write_text(json.dumps(self.transcript, indent=2) + '\n', encoding='utf-8')
            self.errors.seek(0)
            (EVIDENCE / (label + '.stderr')).write_bytes(self.errors.read())
            self.errors.close()


class NativeHostTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='openbexi native host ')
        self.project = Path(self.directory.name)
        self.client = Client(self.project)

    def tearDown(self):
        try:
            self.client.close(self._testMethodName)
        finally:
            self.directory.cleanup()

    def write(self, name, content):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def test_native_run_explicit_import_and_args(self):
        path = self.write('ordinary.py', '''from spell.lang.functions import Display
from spell.runtime import ARGS, IVARS
from pathlib import Path
IVARS['answer'] = ARGS['value'] * 2
count = Path('execution-count.txt')
count.write_text(str(int(count.read_text()) + 1 if count.exists() else 1))
Display('NATIVE_HOST_RESULT_' + str(IVARS['answer']))
Path('result.txt').write_text(str(IVARS['answer']))
''')
        original = path.read_bytes()
        self.client.launch('ordinary.py', noDebug=True, spellArguments={'value': 21})
        self.client.request('configurationDone')
        self.assertEqual(self.client.event('exited')['exitCode'], 0)
        self.client.event('terminated')
        self.assertEqual(self.client.read_file('result.txt'), '42')
        self.assertEqual(self.client.read_file('execution-count.txt'), '1')
        self.assertEqual(path.read_bytes(), original)
        self.assertTrue(any(m.get('event') == 'output' and 'NATIVE_HOST_RESULT_42' in m['body']['output']
                            for m in self.client.transcript))

    def test_breakpoint_variables_edit_step_resume(self):
        path = self.write('control.py', '''from spell.lang.functions import Display
value = 21
checkpoint = value + 1
answer = checkpoint + 1
Display('DEBUG_RESULT_' + str(answer))
assert answer == 42
''')
        self.client.launch('control.py')
        result = self.client.request('setBreakpoints', source={'path': str(path)}, breakpoints=[{'line': 3}])
        self.assertTrue(result['breakpoints'][0]['verified'])
        self.client.request('configurationDone')
        self.client.event('stopped')
        frames = self.client.request('stackTrace', threadId=1)['stackFrames']
        self.assertEqual(frames[0]['line'], 3)
        self.assertEqual(Path(frames[0]['source']['path']), path)
        self.client.request('scopes', frameId=frames[0]['id'])
        values = self.client.request('variables', variablesReference=1)['variables']
        self.assertEqual(next(item['value'] for item in values if item['name'] == 'value'), '21')
        changed = self.client.request('setVariable', variablesReference=1, name='value', value='40')
        self.assertEqual(changed['value'], '40')
        self.client.request('setBreakpoints', source={'path': str(path)}, breakpoints=[])
        self.client.request('stepIn', threadId=1)
        self.client.event('stopped')
        frames = self.client.request('stackTrace', threadId=1)['stackFrames']
        self.assertEqual(frames[0]['line'], 4)
        self.client.request('continue', threadId=1)
        self.assertEqual(self.client.event('exited')['exitCode'], 0)
        self.client.event('terminated')

    def test_error_reported_and_cleanup(self):
        self.write('failure.py', '''from spell.lang.functions import Display
from pathlib import Path
try:
    raise ValueError('native host intentional failure')
finally:
    Path('closed.txt').write_text('cleaned')
''')
        self.client.launch('failure.py')
        self.client.request('configurationDone')
        self.assertEqual(self.client.event('exited')['exitCode'], 1)
        self.client.event('terminated')
        self.assertEqual(self.client.read_file('closed.txt'), 'cleaned')
        self.assertTrue(any(m.get('event') == 'output' and 'native host intentional failure' in m['body']['output']
                            for m in self.client.transcript))

    def test_nested_source_stack_and_local_edit(self):
        path = self.write('nested folder/control.py', '''from spell.lang.functions import Display
def calculate(value):
    local_value = value + 1
    answer = local_value + 1
    return answer
answer = calculate(20)
Display('NESTED_RESULT_' + str(answer))
assert answer == 42
''')
        self.client.launch('nested folder/control.py')
        result = self.client.request('setBreakpoints', source={'path': str(path)},
                                     breakpoints=[{'line': 4}, {'line': 999}])
        self.assertFalse(result['breakpoints'][1]['verified'])
        self.client.request('configurationDone')
        self.client.event('stopped')
        frames = self.client.request('stackTrace', threadId=1)['stackFrames']
        self.assertGreaterEqual(len(frames), 2)
        self.assertEqual(Path(frames[0]['source']['path']), path)
        self.assertEqual(frames[0]['line'], 4)
        values = self.client.request('variables', variablesReference=1)['variables']
        self.assertEqual(next(item['value'] for item in values if item['name'] == 'local_value'), '21')
        self.client.request('setVariable', variablesReference=1, name='local_value', value='41')
        self.client.request('continue', threadId=1)
        self.assertEqual(self.client.event('exited')['exitCode'], 0)
        self.client.event('terminated')

    def test_pause_and_stop_runs_finally(self):
        self.write('pause.py', '''import time
from pathlib import Path
from spell.lang.functions import Display
counter = 0
try:
    Display('LOOP_READY')
    while True:
        counter += 1
        time.sleep(0.02)
finally:
    Path('closed.txt').write_text(str(counter))
''')
        self.client.launch('pause.py')
        self.client.request('configurationDone')
        while 'LOOP_READY' not in self.client.event('output').get('output', ''):
            pass
        self.client.request('pause', threadId=1)
        self.client.event('stopped')
        before = self.client.request('variables', variablesReference=1)['variables']
        time.sleep(.15)
        after = self.client.request('variables', variablesReference=1)['variables']
        self.assertEqual(next(v['value'] for v in before if v['name'] == 'counter'),
                         next(v['value'] for v in after if v['name'] == 'counter'))
        self.client.request('disconnect', terminateDebuggee=True)
        self.assertEqual(self.client.process.wait(timeout=15), 0)
        self.assertTrue(self.client.read_file('closed.txt').isdigit())

    def test_native_prompt_answer(self):
        self.write('prompt.py', '''from spell.lang.functions import Prompt, Display
from spell.lang.constants import YES_NO
from spell.lang.modifiers import Type
answer = Prompt('Continue native host test?', {Type:YES_NO})
assert answer is True
Display('PROMPT_ANSWERED')
''')
        self.client.launch('prompt.py')
        self.client.request('configurationDone')
        prompt = self.client.event('openbexi/inputRequest')
        self.assertEqual(prompt['text'], 'Continue native host test?')
        self.client.request('openbexi/input', text='0')
        self.assertEqual(self.client.event('exited')['exitCode'], 0)
        self.client.event('terminated')

    def test_burst_output_keeps_order_and_final_marker(self):
        self.write('burst.py', "from spell.lang.functions import Display\nfor index in range(1200):\n    Display('BURST_%04d' % index)\nDisplay('BURST_COMPLETE')\n")
        self.client.launch('burst.py', noDebug=True)
        self.client.request('configurationDone')
        self.assertEqual(self.client.event('exited')['exitCode'], 0)
        self.client.event('terminated')
        output = ''.join(m['body']['output'] for m in self.client.transcript if m.get('event') == 'output')
        cursor = -1
        for index in range(1200):
            marker = 'BURST_%04d' % index
            self.assertEqual(output.count(marker), 1, marker)
            following = output.index(marker)
            self.assertGreater(following, cursor)
            cursor = following
        self.assertGreater(output.index('BURST_COMPLETE'), cursor)

    def test_eof_while_running_executes_finally_and_reaps(self):
        self.write('eof.py', "import time\nfrom pathlib import Path\nfrom spell.lang.functions import Display\ntry:\n    Display('EOF_READY')\n    while True:\n        time.sleep(0.01)\nfinally:\n    Path('closed.txt').write_text('eof-cleanup')\n")
        self.client.launch('eof.py', noDebug=True)
        self.client.request('configurationDone')
        while 'EOF_READY' not in self.client.event('output')['output']:
            pass
        self.client.process.stdin.close()
        self.assertEqual(self.client.process.wait(timeout=20), 0)
        self.assertEqual(self.client.read_file('closed.txt'), 'eof-cleanup')

    def test_failed_launch_then_ordinary_launch(self):
        self.write('valid.py', "from spell.lang.functions import Display\nDisplay('AFTER_FAILED_LAUNCH')\n")
        self.client.start()
        self.client.request('initialize', adapterID='spell')
        self.client.request('launch', success=False, project=str(self.project), program=str(self.project / 'absent.py'))
        self.client.request('launch', project=str(self.project), program=str(self.project / 'valid.py'))
        self.client.event('initialized')
        self.client.request('configurationDone')
        self.assertEqual(self.client.event('exited')['exitCode'], 0)
        self.client.event('terminated')

    def test_malformed_protocol_stops_with_error(self):
        self.client.start()
        self.client.process.stdin.write(b'Content-Length: 1\r\nContent-Length: 2\r\n\r\n{}')
        self.client.process.stdin.flush()
        self.assertEqual(self.client.event('exited')['exitCode'], 1)
        self.client.event('terminated')
        self.assertEqual(self.client.process.wait(timeout=10), 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default=IMAGE)
    options = parser.parse_args()
    IMAGE = options.image
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeHostTests))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / 'result.json').write_text(json.dumps({
        'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'image': subprocess.check_output(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], text=True).strip(),
        'inputs': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted((ROOT / 'host_runtime').rglob('*')) if p.is_file() and '__pycache__' not in p.parts},
    }, indent=2) + '\n')
    raise SystemExit(not result.wasSuccessful())
