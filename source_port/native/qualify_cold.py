"""Original manager cold execution with live CPython frames. SPDX-License-Identifier: GPL-3.0-or-later."""
import gc
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import weakref

spec = importlib.util.spec_from_file_location('_spell_analysis_qualification',
    next(Path('/out').glob('_spell_analysis_qualification*.so')))
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class ColdExecution(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.file = Path(self.directory.name) / 'procedure.py'
        self.handle = native.manager_create(None)
        self.globals = vars(sys.modules['__main__'])
        self.globals['_cold_native'] = native
        self.original_file = self.globals.get('__file__')

    def tearDown(self):
        native.manager_close(self.handle)
        for key in list(self.globals):
            if key.startswith('_cold_'): self.globals.pop(key)
        self.globals['__file__'] = self.original_file
        self.directory.cleanup()

    def load(self, source):
        self.file.write_text(source, encoding='utf-8')
        native.manager_initialize(self.handle, str(self.file))

    def run_code(self, source, observer=None):
        self.load(source)
        return native.manager_execute(self.handle, observer)

    def test_nested_functions_and_actual_live_frame_events(self):
        status, events = self.run_code('''
def _cold_child(x):
    return x * 2
def _cold_parent():
    return _cold_child(21)
_cold_result = _cold_parent()
''')
        self.assertEqual(status, 0)
        self.assertEqual(self.globals['_cold_result'], 42)
        self.assertEqual([name for event,name,_ in events if event == 0], ['<module>','_cold_parent','_cold_child'])
        self.assertEqual([name for event,name,_ in events if event == 3], ['_cold_child','_cold_parent','<module>'])

    def test_exception_handlers_and_finally_keep_original_semantics(self):
        status, _ = self.run_code('''
_cold_events = []
try:
    raise ValueError('handled')
except ValueError as error:
    _cold_events.append(str(error))
finally:
    _cold_events.append('finally')
''')
        self.assertEqual(status, 0)
        self.assertEqual(self.globals['_cold_events'], ['handled','finally'])

    def test_uncaught_error_reports_original_status_and_runs_finally(self):
        status, _ = self.run_code('''
_cold_events = []
try:
    raise ValueError('failure')
finally:
    _cold_events.append('finally')
''')
        self.assertEqual(status, 2)
        self.assertEqual(self.globals['_cold_events'], ['finally'])
        status, _ = self.run_code('_cold_result = 42\n')
        self.assertEqual(status, 0)

    def test_abort_and_terminate_use_original_control_flags(self):
        for terminate, expected in ((False,1),(True,3)):
            status, _ = self.run_code(f'''
_cold_events = []
try:
    _cold_native.manager_stop({terminate})
finally:
    _cold_events.append('finally')
''')
            self.assertEqual(status, expected)
            self.assertEqual(self.globals['_cold_events'], ['finally'])

    def test_live_script_edit_during_nested_execution(self):
        def observe(frame, event):
            if event == 2 and frame.f_code.co_name == '_cold_work' and frame.f_lineno == 4:
                native.manager_script(self.handle, 'value=40')
        status, _ = self.run_code('def _cold_work():\n value=1\n unused=0\n return value+2\n_cold_result=_cold_work()\n', observe)
        self.assertEqual(status, 0)
        self.assertEqual(self.globals['_cold_result'], 42)

    def test_script_before_first_execution_and_failed_reload(self):
        self.load('_cold_result = _cold_input + 2\n')
        native.manager_script(self.handle, '_cold_input=40')
        self.assertEqual(native.manager_execute(self.handle)[0], 0)
        self.assertEqual(self.globals['_cold_result'], 42)
        with self.assertRaises(RuntimeError): self.load('broken =\n')
        with self.assertRaisesRegex(RuntimeError, 'No current frame'):
            native.manager_script(self.handle, '_cold_result=0')
        with self.assertRaises(RuntimeError): native.manager_execute(self.handle)
        self.assertEqual(self.globals['_cold_result'], 42)

    def test_repeated_reload_releases_previous_code_and_frames(self):
        refs = []
        def observe(frame, event):
            if event == 0: refs.append(weakref.ref(frame.f_code))
        for n in range(300):
            self.assertEqual(self.run_code(f'_cold_result={n}\n', observe)[0], 0)
        self.assertEqual(self.globals['_cold_result'], 299)
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs[:-1]))
        self.assertIsNotNone(refs[-1]())

    def test_trace_is_restored_after_success_and_failure(self):
        def previous(frame, event, arg): return previous
        sys.settrace(previous)
        try:
            self.assertEqual(self.run_code('_cold_result=42\n')[0], 0)
            self.assertIs(sys.gettrace(), previous)
            self.assertEqual(self.run_code('raise ValueError("failure")\n')[0], 2)
            self.assertIs(sys.gettrace(), previous)
        finally:
            sys.settrace(None)


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ColdExecution))
Path('/out/cold-runtime.json').write_text(json.dumps({
    'tests':result.testsRun, 'failures':len(result.failures), 'errors':len(result.errors), 'skips':len(result.skipped),
    'address_sanitizer':True, 'undefined_behavior_sanitizer':True, 'leak_sanitizer':False,
    'trace_dispatch':'qualification adapter calling original manager public callbacks',
    'full_spell_executor_qualified':False},indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
