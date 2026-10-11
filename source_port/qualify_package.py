"""Exercise the installed wheel in a fresh image with no source/build tree.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

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
        assert cls.doctor['version'] == '0.2.0a2'
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


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InstalledRuntime))
    report = {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
              'skips': len(result.skipped), 'wheel': WHEEL.name,
              'wheel_sha256': hashlib.sha256(WHEEL.read_bytes()).hexdigest(),
              'no_build_tree': not Path('/source').exists() and not Path('/out').exists()}
    if result.wasSuccessful():
        run([ENV / 'bin/python', '-m', 'pip', 'uninstall', '-y', 'openbexi-spell-source'])
        for path in (ENV / 'bin/spell-native', ENV / 'bin/spell-native-python'):
            assert not path.exists(), path
        run([ENV / 'bin/python', '-I', '-c', "import importlib.util; assert importlib.util.find_spec('spell') is None; assert 6*7==42"])
        report['uninstall_preserves_plain_python'] = True
    (OUTPUT / 'installed-runtime.json').write_text(json.dumps(report, indent=2) + '\n')
    # Always export failures; promotion is an explicit recorder gate.
