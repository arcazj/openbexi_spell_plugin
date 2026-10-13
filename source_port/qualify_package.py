"""Exercise the installed wheel in a fresh image with no source/build tree.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
import xml.etree.ElementTree as ET
import zipfile

OUTPUT = Path('/qualification')
OUTPUT.mkdir(exist_ok=True)
ENV = Path('/opt/spell-test-env')
WHEEL, = Path('/distribution').glob('*.whl')


def run(arguments, **kwargs):
    result = subprocess.run([str(arg) for arg in arguments], capture_output=True, text=True,
                            timeout=60, **kwargs)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    if 'AddressSanitizer:' in result.stderr or 'runtime error:' in result.stderr:
        raise AssertionError(result.stderr)
    return result.stdout


class InstalledRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert not Path('/source').exists() and not Path('/out').exists()
        run([sys.executable, '-m', 'venv', ENV])
        run([ENV / 'bin/python', '-m', 'pip', 'install', '--no-index', '--find-links=/wheelhouse', WHEEL])
        cls.doctor = json.loads(run([ENV / 'bin/spell-native', 'doctor']))
        assert cls.doctor['environment'] == str(ENV)
        assert cls.doctor['version'] == '0.3.0'
        cls.example = json.loads(run([ENV / 'bin/spell-native', 'init-example', OUTPUT / 'example']))

    def test_installed_native_executor_uses_selected_environment(self):
        procedure = OUTPUT / 'native-installed.py'
        procedure.write_text('''import builtins,sys
from pathlib import Path
import spell,libSPELL_DTA_v3
from spell.runtime import ARGS,IVARS
from spell.lang.functions import Display
assert sys.prefix == '/opt/spell-test-env', sys.prefix
assert Path(spell.__file__).is_relative_to(sys.prefix), spell.__file__
assert Path(libSPELL_DTA_v3.__file__).is_relative_to(sys.prefix), libSPELL_DTA_v3.__file__
assert isinstance(ARGS,libSPELL_DTA_v3.DataContainer)
assert ARGS['value'] == 21
IVARS['answer'] = ARGS['value'] * 2
assert IVARS['answer'] == 42
assert all(name not in vars(builtins) for name in ('Display','ARGS','Step'))
Display('INSTALLED_NATIVE_RESULT_42')
''')
        text = run([ENV / 'bin/spell-native', 'run', '-f', procedure,
                    '-c', self.example['config'], '-n', 'example', '-g', "{'value':21}"],
                   env=dict(os.environ, **self.example['environment']))
        (OUTPUT / 'installed-executor.log').write_text(text)
        self.assertIn('[ DISPLAY ] INSTALLED_NATIVE_RESULT_42', text)
        self.assertIn('[ STATUS  ] FINISHED', text)

    def test_native_python_import_and_type_identity(self):
        code = """import json,sys
from pathlib import Path
import libSPELL_DTA_v3 as dta
from spell.lib.adapter.data import DataContainer
assert DataContainer is dta.DataContainer
assert Path(dta.__file__).is_relative_to(sys.prefix)
assert dta.__file__.endswith('libspell_executor313.so')
assert dta.DataContainer.__module__ == 'libSPELL_DTA_v3'
print(json.dumps({'native':dta.__file__,'prefix':sys.prefix}))
"""
        data = json.loads(run([ENV / 'bin/spell-native-python', '-I', '-c', code]))
        self.assertEqual(data['prefix'], str(ENV))

    def test_installed_listener_context_and_server_executor(self):
        example=self.example
        server=ET.parse(example['config'])
        server.find("./listener/property[@name='ListenerPort']").text='22980'
        server.find("./listener/property[@name='ContextListenerPort']").text='22981'
        server.write(example['config'],encoding='utf-8')
        data=Path(example['environment']['SPELL_DATA'])
        result_file=OUTPUT/'installed-context-result.txt'
        (data/'Procedures/installed_native.py').write_text('''##########
# NAME: Installed original context procedure
# SPACECRAFT: Y
# PYTHON VERSION: 3
##########
import sys
from pathlib import Path
from spell.runtime import ARGS,IVARS
from spell.lang.functions import Display
assert sys.prefix == '/opt/spell-test-env', sys.prefix
IVARS['answer']=ARGS['value']*2
Display('INSTALLED_CONTEXT_RESULT_42')
Path('/qualification/installed-context-result.txt').write_text(str(IVARS['answer']))
''')
        env=dict(os.environ,**example['environment'])
        with (OUTPUT/'installed-listener.log').open('w') as log:
            listener=subprocess.Popen([ENV/'bin/spell-native','listener','-c',example['config']],
                env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                time.sleep(.5)
                peer_env=dict(env,LD_LIBRARY_PATH=str(Path(self.doctor['native_root'])/'bin'),
                    ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
                    UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
                text=run(['/qualification-input/installed_peer','22980'],env=peer_env)
                (OUTPUT/'installed-peer.log').write_text(text)
                self.assertIn('INSTALLED_LISTENER_CONTEXT_EXECUTOR_CLOSED',text)
                self.assertEqual(result_file.read_text(),'42')
                listener.terminate()
                self.assertEqual(listener.wait(timeout=10),0)
            finally:
                try: os.killpg(listener.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                listener.wait(timeout=5)
        logs=(OUTPUT/'installed-listener.log').read_text()
        self.assertNotIn('AddressSanitizer:',logs)
        self.assertNotIn('runtime error:',logs)
        native='\n'.join(p.read_text() for p in Path(example['environment']['SPELL_LOG']).glob('*.log'))
        self.assertIn('Executor process finished: installed_native#1',native)
        self.assertNotIn('try kill',native)
        self.assertNotIn('killing instead',native)

    def test_installed_service_checkpoint_request_fails_explicitly(self):
        checkpoint=OUTPUT/'service-checkpoint.dat'
        checkpoint.write_bytes(b'preserve checkpoint')
        result=subprocess.run([ENV/'bin/spell-native','service','-p','unstarted-service',
            '-c',self.example['config'],'-n','example','-r',checkpoint],
            capture_output=True,text=True,timeout=10,
            env=dict(os.environ,**self.example['environment']))
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('Checkpoint recovery is unavailable for native services',result.stderr)
        self.assertEqual(checkpoint.read_bytes(),b'preserve checkpoint')

    def test_plain_python_requires_diagnostic_launcher(self):
        result = subprocess.run([ENV / 'bin/python', '-I', '-c', 'import libSPELL_DTA_v3'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn('requires spell-native-python or spell-native run', result.stderr)
        self.assertNotIn('AddressSanitizer:', result.stderr)

    def test_existing_example_directory_is_preserved(self):
        target = OUTPUT / 'existing'
        target.mkdir()
        marker = target / 'user.txt'
        marker.write_text('preserved')
        result = subprocess.run([ENV / 'bin/spell-native', 'init-example', target],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), 'preserved')
        self.assertEqual(list(target.iterdir()), [marker])

    def test_provenance_matches_installed_native_files(self):
        root = Path(self.doctor['native_root'])
        manifest = json.loads((root / 'manifest.json').read_text())
        for name, expected in manifest['native_artifacts'].items():
            self.assertEqual(hashlib.sha256((root / 'bin' / name).read_bytes()).hexdigest(), expected)
        archive = root / 'provenance/SPELL2.6.10-src.zip'
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), manifest['archive_sha256'])
        self.assertTrue((root / 'provenance/source_port/native_patches.py').is_file())
        self.assertTrue((root / 'provenance/source_port/distribution-build.Dockerfile').is_file())

    def test_complete_wheel_record_and_installed_composition(self):
        root = Path(self.doctor['native_root'])
        site = root.parent
        manifest = json.loads((root/'manifest.json').read_text())
        with zipfile.ZipFile(WHEEL) as archive:
            record, = [name for name in archive.namelist() if name.endswith('.dist-info/RECORD')]
            rows = list(csv.reader(io.StringIO(archive.read(record).decode())))
            self.assertEqual(len(rows), len(archive.namelist()))
            self.assertEqual({row[0] for row in rows}, set(archive.namelist()))
            for name, expected, size in rows:
                if name == record:
                    self.assertEqual((expected, size), ('', ''))
                    continue
                contents = archive.read(name)
                encoded = base64.urlsafe_b64encode(hashlib.sha256(contents).digest()).rstrip(b'=').decode()
                self.assertEqual(expected, 'sha256='+encoded, name)
                self.assertEqual(int(size), len(contents), name)
                self.assertEqual((site/name).read_bytes(), contents, name)
        compositions = manifest.get('composition', {})
        # Legacy diagnostic wheels still use this installed gate. An integrated
        # manifest must carry both chains, each matching the installed payload.
        if compositions:
            self.assertEqual(set(compositions), {'native', 'python'})
            self.assertEqual(compositions['native']['recipes'], compositions['python']['recipes'])
            for kind, composition in compositions.items():
                evidence = root/('provenance/integrated-'+kind)
                report = (evidence/'manifest.json').read_bytes()
                self.assertEqual(hashlib.sha256(report).hexdigest(), composition['manifest_sha256'])
                self.assertEqual(json.loads(report), {k:v for k,v in composition.items() if k != 'manifest_sha256'})
                for name, row in composition['sources'].items():
                    for label, expected in row.items():
                        self.assertEqual(hashlib.sha256((evidence/label.removesuffix('_sha256')/name).read_bytes()).hexdigest(), expected)
                    if kind == 'python':
                        self.assertEqual(hashlib.sha256((site/name).read_bytes()).hexdigest(), row['patched_sha256'])
                for name, row in composition['recipes'].items():
                    self.assertEqual(hashlib.sha256((evidence/'recipes'/name).read_bytes()).hexdigest(), row['sha256'])
            checkpoint = compositions['native']['checkpoint']['integrated_identity'].encode()
            self.assertIn(checkpoint, (root/'bin/libspell_executor313.so').read_bytes())


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InstalledRuntime))
    report = {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
              'skips': len(result.skipped), 'wheel': WHEEL.name,
              'wheel_sha256': hashlib.sha256(WHEEL.read_bytes()).hexdigest(),
              'installed_peer_sha256':hashlib.sha256(Path('/qualification-input/installed_peer').read_bytes()).hexdigest(),
              'no_build_tree': not Path('/source').exists() and not Path('/out').exists()}
    if result.wasSuccessful():
        run([ENV / 'bin/python', '-m', 'pip', 'uninstall', '-y', 'openbexi-spell-source'])
        for path in (ENV / 'bin/spell-native', ENV / 'bin/spell-native-python'):
            assert not path.exists(), path
        run([ENV / 'bin/python', '-I', '-c', "import importlib.util; assert importlib.util.find_spec('spell') is None; assert 6*7==42"])
        report['uninstall_preserves_plain_python'] = True
    # The example and its links belong only to this disposable test. Preserve
    # link targets as evidence after testing/removal, so the local Docker
    # exporter works on Windows without symlink-creation privileges.
    report['installed_example_links']={}
    for name in ('SPELL-Executor','SPELL-Executor_v3'):
        path=OUTPUT/'example/bin'/name
        if path.is_symlink():
            report['installed_example_links'][name]=os.readlink(path)
            path.unlink()
    (OUTPUT / 'installed-runtime.json').write_text(json.dumps(report, indent=2) + '\n')
    # Always export failures; promotion is an explicit recorder gate.
