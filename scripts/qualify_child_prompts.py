"""Real native DAP checks for successive and overlapping parent/child prompts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

import qualify_host_adapter as host


class ChildPromptTests(host.NativeHostTests):
    # The base supplies ownership and retained DAP transcripts. Only the two
    # cases selected in main are run; its full host suite is qualified separately.
    def test_successive_child_then_parent_prompts_reject_stale_answer(self):
        self.write('main.py', '''from spell.lang.functions import StartProc, Prompt
from spell.lang.constants import YES_NO
from pathlib import Path
assert StartProc('child', HandleError=False) is True
assert Prompt('Parent last', Type=YES_NO) is False
Path('parent.txt').write_text('answered no')
''')
        self.write('child.py', '''from spell.lang.functions import Prompt
from spell.lang.constants import YES_NO
from pathlib import Path
assert Prompt('Child first', Type=YES_NO) is True
assert Prompt('Child second', Type=YES_NO) is False
Path('child.txt').write_text('answered yes then no')
''')
        self.client.launch('main.py', noDebug=True)
        self.client.request('configurationDone')
        first = self.client.event('openbexi/inputRequest')
        self.assertEqual(first['text'], 'Child first')
        self.client.request('openbexi/input', text='0', promptId=first['promptId'])
        second = self.client.event('openbexi/inputRequest')
        self.assertEqual(second['text'], 'Child second')
        self.assertNotEqual(first['promptId'], second['promptId'])
        self.client.request('openbexi/input', text='0', promptId=first['promptId'], success=False)
        repeated = self.client.event('openbexi/inputRequest')
        self.assertEqual(repeated, second)
        self.client.request('openbexi/input', text='1', promptId=second['promptId'])
        parent = self.client.event('openbexi/inputRequest')
        self.assertEqual(parent['text'], 'Parent last')
        self.assertEqual(parent['procedureId'], 'main#1')
        self.client.request('openbexi/input', text='1', promptId=parent['promptId'])
        self.assertEqual(self.client.event('exited')['exitCode'], 0)
        self.client.event('terminated')
        self.assertEqual(self.client.read_file('parent.txt'), 'answered no')
        self.assertEqual(self.client.read_file('child.txt'), 'answered yes then no')

    def test_nonblocking_child_and_parent_prompts_preserve_each_answer(self):
        self.write('main.py', '''import time
from pathlib import Path
from spell.lang.functions import StartProc, Prompt
from spell.lang.constants import YES_NO
assert StartProc('child', Blocking=False, HandleError=False) is True
assert Prompt('Parent overlap', Type=YES_NO) is False
while not Path('child.txt').exists():
    time.sleep(0.02)
Path('parent.txt').write_text('answered no')
''')
        self.write('child.py', '''from pathlib import Path
from spell.lang.functions import Prompt
from spell.lang.constants import YES_NO
assert Prompt('Child overlap', Type=YES_NO) is True
Path('child.txt').write_text('answered yes')
''')
        self.client.launch('main.py', noDebug=True)
        self.client.request('configurationDone')
        seen = {}
        for _ in range(2):
            prompt = self.client.event('openbexi/inputRequest')
            text = prompt['text']
            self.assertIn(text, ('Parent overlap', 'Child overlap'))
            self.assertNotIn(text, seen)
            seen[text] = prompt
            self.client.request('openbexi/input', text='1' if text == 'Parent overlap' else '0',
                                promptId=prompt['promptId'])
        self.assertEqual(seen['Parent overlap']['procedureId'], 'main#1')
        self.assertTrue(seen['Child overlap']['procedureId'].startswith('child#'))
        self.assertEqual(self.client.event('exited')['exitCode'], 0)
        self.client.event('terminated')
        self.assertEqual(self.client.read_file('parent.txt'), 'answered no')
        self.assertEqual(self.client.read_file('child.txt'), 'answered yes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    host.IMAGE, host.EVIDENCE = args.image, args.output.resolve()
    names = [name for name in ChildPromptTests.__dict__ if name.startswith('test_')]
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(ChildPromptTests(name) for name in names))
    host.EVIDENCE.mkdir(parents=True, exist_ok=True)
    sources = [*sorted((host.ROOT/'host_runtime').rglob('*')), Path(host.__file__), Path(__file__).resolve()]
    (host.EVIDENCE/'result.json').write_text(json.dumps({
        'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'image': subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip(),
        'inputs': {path.relative_to(host.ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in sources if path.is_file() and '__pycache__' not in path.parts},
        'scope':'Native DAP prompt ownership and ordering; no general child debugger or browser interaction claim.',
    },indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not result.wasSuccessful())
