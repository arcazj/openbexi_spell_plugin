"""Behavioral tests for the standalone native editor exporter (no Docker needed)."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/export_spell_editor.py'
spec = importlib.util.spec_from_file_location('export_spell_editor', SCRIPT)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def declarations(source):
    tree = ast.parse(source)
    names = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        if isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return names


def recorded_files():
    # Source-backed guards are fixtures, not runtime implementations.
    evidence = {
        'spell/__init__.py': '',
        'spell/lang/__init__.py': '',
        'spell/lang/functions.py': 'def Display(*args, **kargs):\n    return helper.execute(*args, **kargs)\n',
        'native/helper_namespace.cpp': 'PyImport_AddModule("spell.runtime")',
        'native/executor_environment.cpp': 'helper.install(args.get(),"ARGS"); helper.install(variables.get(),"IVARS");',
        'native/executor_proc.cpp': 'PyDict_New(); DatabaseConstants::PROC;',
        'native/dta_module.cpp': '"DataContainer" "Var"',
        'native/dta_container_bindings.cpp': '"|s:DataContainer" "OO:set" "O:get"',
        'native/dta_variable_bindings.cpp': 'Expected no positional arguments',
        'upstream/lib/SPELL_EXC/src/SPELLstepPython.C': 'install(Step,"Step")',
        'upstream/lib/SPELL_EXC/src/SPELLgotoPython.C': 'install(Goto,"Goto")',
    }
    return {name: {'source': text, 'sha256': exporter.sha(text.encode())} for name, text in evidence.items()}


class EditorExportTests(unittest.TestCase):
    @staticmethod
    def directory_redirect(path, target):
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(target), str(path))
        else:
            path.symlink_to(target, target_is_directory=True)

    @staticmethod
    def remove_redirect(path):
        if os.name == 'nt':
            path.rmdir()
        else:
            path.unlink()

    def test_generation_preserves_real_api_without_executing_source(self):
        source = '''# Copyright example source owner
raise RuntimeError("generation must not execute this")
from dependency import ActualException
ABORT = 1
def Display(message, options=None, *, Notify=False):
    """Show a procedure message."""
    raise RuntimeError("procedure must not execute")
SendAndVerify = Display
def __getattr__(name):
    return invented_runtime_name(name)
'''
        stub = exporter.generate_stub(source, 'spell/lang/functions.py')
        self.assertEqual(declarations(stub), {'ABORT', 'Display', 'SendAndVerify'})
        self.assertIn('from dependency import ActualException as ActualException', stub)
        self.assertIn('Show a procedure message.', stub)
        self.assertIn('Copyright example source owner', stub)
        self.assertNotIn('invented_runtime_name', stub)
        self.assertNotIn('raise RuntimeError', stub)
        signature = next(node for node in ast.parse(stub).body if isinstance(node, ast.FunctionDef))
        self.assertEqual([arg.arg for arg in signature.args.args], ['message', 'options'])
        self.assertEqual([arg.arg for arg in signature.args.kwonlyargs], ['Notify'])

    def test_class_and_conditional_symbols_preserved(self):
        source = '''if version > 3:
    FLAG = 2
class TIME:
    def __init__(self, value):
        self._value = value
    @staticmethod
    def epoch(seconds):
        return TIME(seconds)
    def rel(self):
        return self._value
NOW = TIME("NOW")
'''
        stub = exporter.generate_stub(source, 'spell/lib/adapter/utctime.py')
        self.assertEqual(declarations(stub), {'FLAG', 'TIME', 'NOW'})
        self.assertIn('NOW: TIME', stub)
        self.assertIn('@staticmethod', stub)
        self.assertIn('_value: _SpellAny', stub)

    def test_lazy_dta_exports_are_finite(self):
        source = '''def __getattr__(name):
    if name in {'DataContainer', 'Var'}:
        from spell.lib.adapter import data
        return getattr(data, name)
    raise AttributeError(name)
'''
        stub = exporter.generate_stub(source, 'spell/lang/constants.py')
        self.assertIn('DataContainer as DataContainer, Var as Var', stub)
        self.assertNotIn('def __getattr__', stub)

    def test_native_bindings_fail_closed_when_image_provenance_changes(self):
        files = recorded_files()
        self.assertIn('spell/runtime.pyi', exporter.native_stubs(files))
        files['native/helper_namespace.cpp']['source'] = 'different runtime namespace'
        with self.assertRaisesRegex(ValueError, 'binding provenance'):
            exporter.native_stubs(files)

    def test_output_contains_only_stubs_and_image_source_identity(self):
        payload = {'files': recorded_files(), 'python': '3.13'}
        files, manifest = exporter.build_definitions(payload, 'sha256:' + '1' * 64, 'native:local')
        self.assertTrue(all(name.endswith('.pyi') or name == 'manifest.json' for name in files))
        self.assertEqual(manifest['image_id'], 'sha256:' + '1' * 64)
        self.assertEqual(manifest['source_sha256']['spell/lang/functions.py'], payload['files']['spell/lang/functions.py']['sha256'])
        for name, digest in manifest['generated_sha256'].items():
            self.assertEqual(exporter.sha(files[name]), digest)
            ast.parse(files[name])
        self.assertEqual(declarations(files['spell/runtime.pyi']), {'Step', 'Goto', 'ARGS', 'IVARS', 'PROC'})
        self.assertEqual(declarations(files['spell/lang/__init__.pyi']), set())

    def test_does_not_replace_unrelated_or_user_edited_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'editor'
            root.mkdir()
            (root / 'my_file.txt').write_text('keep me')
            with self.assertRaisesRegex(ValueError, 'without an editor manifest'):
                exporter.write_definitions(root, {'spell/__init__.pyi': b''})
            self.assertEqual((root / 'my_file.txt').read_text(), 'keep me')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'editor'
            files, _ = exporter.build_definitions({'files': recorded_files(), 'python': '3.13'}, 'test', 'test')
            exporter.write_definitions(root, files)
            (root / 'spell/__init__.pyi').write_text('# my edit')
            with self.assertRaisesRegex(ValueError, 'locally edited'):
                exporter.write_definitions(root, files)
            self.assertEqual((root / 'spell/__init__.pyi').read_text(), '# my edit')

    def test_replacement_removes_stale_generated_modules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'editor'
            payload = {'files': recorded_files(), 'python': '3.13'}
            payload['files']['spell/old.py'] = {'source': 'OLD = 1', 'sha256': exporter.sha(b'OLD = 1')}
            old, _ = exporter.build_definitions(payload, 'old', 'test')
            exporter.write_definitions(root, old)
            del payload['files']['spell/old.py']
            new, _ = exporter.build_definitions(payload, 'new', 'test')
            exporter.write_definitions(root, new)
            self.assertFalse((root / 'spell/old.pyi').exists())
            self.assertEqual(json.loads((root / 'manifest.json').read_text())['image_id'], 'new')

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'editor'
            with self.assertRaisesRegex(ValueError, 'Unsafe generated path'):
                exporter.write_definitions(root, {'../escape': b'bad'})
            self.assertFalse((Path(temporary) / 'escape').exists())

    def test_output_junction_and_redirected_parent_cannot_replace_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            target = base / 'real-parent'
            root = target / 'editor'
            old, _ = exporter.build_definitions({'files': recorded_files(), 'python': '3.13'}, 'old', 'old')
            new, _ = exporter.build_definitions({'files': recorded_files(), 'python': '3.13'}, 'new', 'new')
            exporter.write_definitions(root, old)
            before = (root / 'manifest.json').read_bytes()
            for destination, redirected_target, attempted in (
                    (base / 'linked-output', root, base / 'linked-output'),
                    (base / 'linked-parent', target, base / 'linked-parent/editor'),
                    (base / 'linked-parent', target, base / 'linked-parent/not-yet-created')):
                with self.subTest(path=attempted):
                    self.directory_redirect(destination, redirected_target)
                    try:
                        with self.assertRaisesRegex(ValueError, 'symlink or junction'):
                            exporter.write_definitions(attempted, new)
                        self.assertEqual((root / 'manifest.json').read_bytes(), before)
                        self.assertFalse((target / 'not-yet-created').exists())
                    finally:
                        self.remove_redirect(destination)

    def test_nested_junction_is_not_followed_or_deleted(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / 'editor'
            files, _ = exporter.build_definitions({'files': recorded_files(), 'python': '3.13'}, 'old', 'old')
            exporter.write_definitions(root, files)
            target = base / 'user-data'
            target.mkdir()
            marker = target / 'important.txt'
            marker.write_text('keep me')
            redirected = root / 'redirected'
            self.directory_redirect(redirected, target)
            try:
                with self.assertRaisesRegex(ValueError, 'symlink or junction'):
                    exporter.write_definitions(root, files)
                self.assertEqual(marker.read_text(), 'keep me')
                self.assertTrue(redirected.exists())
            finally:
                self.remove_redirect(redirected)

    def test_extract_pins_image_and_does_not_mount_or_import_spell(self):
        identity = 'sha256:' + 'a' * 64
        completed = [subprocess.CompletedProcess([], 0, identity + '\n', ''),
                     subprocess.CompletedProcess([], 0, json.dumps({'files': recorded_files(), 'python': '3.13'}), '')]
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(exporter.subprocess, 'run', side_effect=completed) as run:
            result = exporter.export('mutable:tag', Path(temporary) / 'editor')
            command = run.call_args_list[1].args[0]
            self.assertIn(identity, command)
            self.assertNotIn('mutable:tag', command)
            self.assertNotIn('--mount', command)
            self.assertNotIn('-v', command)
            self.assertIn('--read-only', command)
            self.assertNotIn('import spell', exporter.EXTRACT)
            self.assertEqual(result['image_id'], identity)


if __name__ == '__main__':
    unittest.main()
