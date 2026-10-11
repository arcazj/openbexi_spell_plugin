"""Original frame manager component checks. SPDX-License-Identifier: GPL-3.0-or-later."""
import builtins
import gc
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
import weakref

spec = importlib.util.spec_from_file_location('_spell_analysis_qualification',
    next(Path('/out').glob('_spell_analysis_qualification*.so')))
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class FrameManager(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.file = Path(self.directory.name) / 'procedure.py'
        self.closed = []
        self.addCleanup(self.close_managers)
        self.addCleanup(native.ws_filter_set, None)

    def close_managers(self):
        for handle in self.closed:
            native.manager_close(handle)

    def execute(self, source, **namespace):
        self.file.write_text(source, encoding='utf-8')
        namespace.update(native=native, sys=sys, own=self.own)
        exec(compile(source, str(self.file), 'exec'), namespace)
        return namespace

    def own(self, frame):
        handle = native.manager_create(frame)
        self.closed.append(handle)
        return handle

    def test_uninitialized_destruction_and_no_current_frame_error(self):
        for _ in range(500):
            handle = native.manager_create(None)
            with self.assertRaisesRegex(RuntimeError, 'No current frame'):
                native.manager_script(handle, 'answer=42')
            native.manager_close(handle)
        with self.assertRaisesRegex(ValueError, 'closed'):
            native.manager_script(handle, 'answer=42')

    def test_live_local_and_cell_edits(self):
        result = self.execute('''
def run():
    local = 3
    cell = 4
    def read(): return cell
    handle = own(sys._getframe())
    native.manager_script(handle, 'local = 20\\ncell = 22')
    return local + read()
answer = run()
''')
        self.assertEqual(result['answer'], 42)

    def test_shadowed_globals_and_explicit_global_statement(self):
        result = self.execute('''
value = 1
def run():
    value = 2
    handle = own(sys._getframe())
    native.manager_script(handle, 'value=10')
    native.manager_script(handle, 'global answer\\nanswer=value+32')
    return value
local_result = run()
''')
        self.assertEqual((result['value'], result['answer'], result['local_result']), (1, 42, 10))

    def test_script_errors_leave_manager_usable(self):
        result = self.execute('''
frame = sys._getframe()
handle = own(frame)
''')
        for source in ['bad =', 'raise ValueError("broken")', '1 / 0']:
            with self.assertRaises(RuntimeError):
                native.manager_script(result['handle'], source)
        native.manager_script(result['handle'], 'answer=42')
        self.assertEqual(result['answer'], 42)

    def test_models_release_exactly_their_frame_references(self):
        result = self.execute('frame = sys._getframe()\n')
        frame = result['frame']
        baseline = sys.getrefcount(frame)
        for _ in range(1000):
            handle = native.manager_create(frame)
            self.assertEqual(sys.getrefcount(frame), baseline + 1)
            native.manager_close(handle)
            self.assertEqual(sys.getrefcount(frame), baseline)

    def test_script_temporary_results_are_released(self):
        values = []
        class Item:
            def __init__(self): values.append(weakref.ref(self))
        result = self.execute('handle = own(sys._getframe())\n', Item=Item)
        for _ in range(500):
            native.manager_script(result['handle'], 'temporary=Item()\ndel temporary')
        gc.collect()
        self.assertEqual(len(values), 500)
        self.assertTrue(all(ref() is None for ref in values))

    def test_database_copy_identity_and_no_extra_references(self):
        marker = object()
        parent = self.execute('handle=own(sys._getframe())\n', SCDB=marker, GDB=marker, PROC=marker)
        child = self.execute('frame=sys._getframe()\n')
        before = sys.getrefcount(marker)
        for _ in range(500): native.manager_copy(parent['handle'], child['frame'])
        self.assertTrue(all(child[key] is marker for key in ('SCDB', 'GDB', 'PROC')))
        self.assertEqual(sys.getrefcount(marker), before + 3)

    def test_missing_databases_and_builtins_fallback(self):
        parent = self.execute('handle=own(sys._getframe())\n')
        child = self.execute('frame=sys._getframe()\n')
        native.manager_copy(parent['handle'], child['frame'])
        self.assertTrue(all(key not in child for key in ('SCDB', 'GDB', 'PROC')))
        marker = object()
        before = sys.getrefcount(marker)
        builtins.SCDB = marker
        try:
            for _ in range(500): native.manager_copy(parent['handle'], child['frame'])
            self.assertIs(child['SCDB'], marker)
            self.assertEqual(sys.getrefcount(marker), before + 2)
        finally:
            del builtins.SCDB

    def test_nested_call_return_releases_child_and_restores_parent(self):
        parent = self.execute('frame=sys._getframe()\nhandle=own(frame)\n')
        child = self.execute('frame=sys._getframe()\n')
        before = sys.getrefcount(child['frame'])
        native.manager_event(parent['handle'], child['frame'], 0) # PyTrace_CALL
        self.assertEqual(sys.getrefcount(child['frame']), before + 1)
        native.manager_script(parent['handle'], 'answer=12')
        self.assertEqual(child['answer'], 12)
        native.manager_event(parent['handle'], child['frame'], 3) # PyTrace_RETURN
        self.assertEqual(sys.getrefcount(child['frame']), before)
        native.manager_script(parent['handle'], 'answer=42')
        self.assertEqual(parent['answer'], 42)

    def test_definitions_copy_does_not_overwrite_or_copy_args(self):
        key = '_qualification_definition'
        # SPELL exports now live in an interpreter-local module, not builtins.
        import types
        main = vars(sys.modules.setdefault('spell.runtime', types.ModuleType('spell.runtime')))
        main[key] = None
        try:
            value = object()
            parent = self.execute('handle=own(sys._getframe())\n', **{key:value, 'ARGS':object()})
            child = self.execute('frame=sys._getframe()\n')
            for _ in range(100): native.manager_definitions(parent['handle'])
            native.manager_copy(parent['handle'], child['frame'])
            self.assertIs(child[key], value)
            self.assertNotIn('ARGS', child)
            child[key] = 42
            native.manager_copy(parent['handle'], child['frame'])
            self.assertEqual(child[key], 42)
        finally:
            del main[key]

    def test_filter_original_categories_and_replacement(self):
        native.ws_filter_set(['old', 'λ'])
        for key, value in [('old', 1), ('λ', 2), ('SCDB', 1), ('GDB', 1), ('PROC', 1),
                           ('module', sys), ('function', lambda: 1), ('type', object)]:
            self.assertTrue(native.ws_filter_test(key, value), key)
        self.assertFalse(native.ws_filter_test('plain', [1, 2]))
        native.ws_filter_set(['new'])
        self.assertFalse(native.ws_filter_test('old', 1))
        self.assertTrue(native.ws_filter_test('new', 1))
        native.ws_filter_set(None)
        self.assertFalse(native.ws_filter_test('new', 1))

    def test_filter_replacement_releases_objects_and_preserves_on_error(self):
        class Key(str): pass
        keys = []
        for _ in range(1000):
            value = Key('key')
            keys.append(weakref.ref(value))
            native.ws_filter_set([value])
        del value
        native.ws_filter_set(['retained'])
        gc.collect()
        self.assertTrue(all(ref() is None for ref in keys))
        with self.assertRaises(RuntimeError): native.ws_filter_set([[]])
        self.assertTrue(native.ws_filter_test('retained', 1))
        with self.assertRaises(RuntimeError): native.ws_filter_test([], 1)


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FrameManager))
Path('/out/manager-runtime.json').write_text(json.dumps({
    'tests':result.testsRun, 'failures':len(result.failures), 'errors':len(result.errors), 'skips':len(result.skipped),
    'address_sanitizer':True, 'undefined_behavior_sanitizer':True, 'leak_sanitizer':False,
    'component_scope':'original manager public methods; watch/resource notifications disabled',
    'full_spell_executor_qualified':False}, indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
