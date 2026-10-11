"""Independent native UTIL behavior checks. SPDX-License-Identifier: GPL-3.0-or-later."""
import gc
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
import weakref

extension = next(Path('/out').glob('_spell_util_qualification*.so'))
spec = importlib.util.spec_from_file_location('_spell_util_qualification', extension)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeUtil(unittest.TestCase):
    def test_exception_location_uses_real_traceback_line(self):
        namespace={}
        exec(compile('def fail():\n    marker=42\n    raise ValueError(marker)\n',
            'traceback-location.py','exec'),namespace)
        result=native.scope(namespace['fail'])
        self.assertEqual(result[0],7,result)
        self.assertIn("file 'traceback-location.py', line 3",result[1])
        self.assertNotIn('line -1',result[1])

    def test_created_procedure_frames_release_code_after_repeated_loads(self):
        main = vars(sys.modules['__main__'])
        filename = main.get('__file__')
        try:
            refs=[]
            for index in range(2000):
                code=compile('value=1', 'procedure.py', 'exec')
                refs.append(weakref.ref(code))
                frame=native.make_frame(f'procedure-{index}.py', code, False)
                self.assertIs(frame.f_code, code)
                self.assertIs(frame.f_globals, main)
                self.assertIs(frame.f_locals, main)
                self.assertEqual(main['__file__'], f'procedure-{index}.py')
                del frame,code
            gc.collect()
            self.assertTrue(all(ref() is None for ref in refs))
        finally:
            if filename is None: main.pop('__file__',None)
            else: main['__file__']=filename

    def test_created_function_frames_keep_original_namespace_and_balance_ownership(self):
        refs=[]
        for _ in range(1000):
            env={}
            exec(compile('def run():\n return 42\n','function.py','exec'),env)
            function=env.pop('run')
            refs.append(weakref.ref(function.__code__))
            count=sys.getrefcount(env)
            frame=native.make_frame('function.py',function,True)
            self.assertIs(frame.f_code,function.__code__)
            self.assertIs(frame.f_globals,env)
            del frame
            self.assertEqual(sys.getrefcount(env),count)
            del function,env
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))

    def test_frame_factory_rejects_invalid_function_inputs(self):
        for value in (None, 42, len, object()):
            with self.assertRaisesRegex(RuntimeError,'Expected a Python function'):
                native.make_frame('invalid.py',value,True)
        with self.assertRaises(TypeError):
            native.make_frame('invalid.py',None,False)

    def test_frame_metadata_live_nested_frames_and_released_code(self):
        source = 'import sys\ndef nested():\n    return sys._getframe()\nframe = nested()\n'
        env = {}
        code = compile(source, '/out/通信.py', 'exec')
        exec(code, env)
        frame = env.pop('frame')
        expected = (frame.f_code, frame.f_code.co_filename, 'nested', frame.f_lineno, frame.f_lasti)
        initial_refs = sys.getrefcount(frame.f_code)
        for _ in range(2000):
            self.assertEqual(native.frame_metadata(frame), expected)
        self.assertEqual(sys.getrefcount(frame.f_code), initial_refs)
        ref = weakref.ref(frame.f_code)
        env.clear()
        del frame, expected, code
        gc.collect()
        self.assertIsNone(ref())
        with self.assertRaises(TypeError):
            native.frame_metadata(None)

    def test_frame_metadata_on_each_real_trace_event(self):
        code = compile('def f():\n    x=1\n    raise ValueError(x)\ntry:\n    f()\nexcept ValueError:\n    pass\n', '<metadata-trace>', 'exec')
        observations = []
        def trace(frame, event, arg):
            if frame.f_code.co_filename == '<metadata-trace>':
                observations.append(event)
                self.assertEqual(native.frame_metadata(frame),
                    (frame.f_code, frame.f_code.co_filename, frame.f_code.co_name, frame.f_lineno, frame.f_lasti))
            return trace
        previous = sys.gettrace()
        try:
            sys.settrace(trace)
            exec(code, {})
        finally:
            sys.settrace(previous)
        self.assertEqual(set(observations), {'call', 'line', 'return', 'exception'})

    def test_compiler_executes_unicode_nested_code(self):
        source = "label = '通信 🛰'\ndef function(x):\n    return [i*i for i in range(x)]\nresult = function(5)\n"
        code = native.compile(source)
        self.assertIsInstance(code, types.CodeType)
        env = {}
        exec(code, env)
        self.assertEqual(env['label'], '通信 🛰')
        self.assertEqual(env['result'], [0, 1, 4, 9, 16])
        self.assertEqual(code.co_filename, '<string>')

    def test_compiler_reports_syntax_and_null_errors(self):
        for source in ('def broken(:\n', 'x = 1\x00\ny = 2'):
            result = native.compile(source)
            self.assertEqual(result[0], 5, result)
            self.assertIn('Syntax error', result[1])
        self.assertIsInstance(native.compile('x=2'), types.CodeType)

    def test_file_compilation_preserves_filename(self):
        path = Path('/out/通信.py')
        path.write_text('value = 42\n', encoding='utf-8')
        code = native.compile_file(str(path))
        self.assertEqual(code.co_filename, str(path))
        env = {'exit': None}  # Original procedure reader appends the exit name.
        exec(code, env)
        self.assertEqual(env['value'], 42)
        self.assertEqual(native.compile_file('/out/missing.py')[0], 11)

    def test_python_exception_categories_and_traceback(self):
        cases = [(ImportError,0),(IndexError,1),(KeyError,2),(MemoryError,3),
                 (NameError,4),(SyntaxError,5),(TypeError,6),(ValueError,7),(RuntimeError,8)]
        for cls, expected in cases:
            def fail():
                raise cls('通信 failure')
            result = native.scope(fail)
            self.assertEqual(result[0], expected, result)
            self.assertIn('通信 failure', result[2])
            self.assertIn('qualify_util.py', result[1])
        self.assertIsNone(native.scope(lambda: None))

    def test_exception_with_broken_str_does_not_mask_original_type(self):
        class BadString(ValueError):
            def __str__(self):
                raise RuntimeError('format failed')
        def fail():
            raise BadString()
        self.assertEqual(native.scope(fail)[0], 7)
        self.assertIsNone(native.scope(lambda: None))

    def test_errors_release_tracebacks_and_payloads(self):
        class Payload: pass
        refs = []
        def fail():
            payload = Payload()
            refs.append(weakref.ref(payload))
            raise ValueError('release locals')
        for _ in range(2000):
            self.assertEqual(native.scope(fail)[0], 7)
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))

    def test_native_thread_error_paths_release_gil(self):
        self.assertEqual(native.thread_errors(), (200, True))

    def test_host_interpreter_survives_helper_finalize(self):
        original_path = sys.path.copy()
        original_argv = sys.argv.copy()
        original_builtins = set(vars(__import__('builtins')))
        self.assertEqual(native.lifecycle(), (True, True))
        self.assertEqual(sys.path, original_path)
        self.assertEqual(sys.argv, original_argv)
        self.assertEqual(set(vars(__import__('builtins'))), original_builtins)
        self.assertEqual(eval('6 * 7'), 42)

    def test_unicode_path_and_duplicate_handling(self):
        path = '/out/通信 procedure folder'
        original = sys.path.copy()
        try:
            self.assertIsNone(native.add_path(path))
            self.assertIsNone(native.add_path(path))
            self.assertEqual(sys.path, original+[path])
        finally:
            sys.path[:] = original

    def test_new_instance_owns_one_reference(self):
        class Item:
            def __init__(self, value=0): self.value = value
        args = (42,)
        baseline = sys.getrefcount(args)
        refs = []
        for _ in range(2000):
            instance = native.new_instance(Item, args, None)
            self.assertEqual(instance.value, 42)
            refs.append(weakref.ref(instance))
            del instance
        gc.collect()
        self.assertEqual(sys.getrefcount(args), baseline)
        self.assertTrue(all(ref() is None for ref in refs))
        self.assertEqual(native.new_instance(Item, None, {'value': 17}).value, 17)

    def test_public_line_jump_skips_statement(self):
        source = 'def target():\n    value = 1\n    value = 999\n    return value\n'
        env = {}
        exec(native.compile(source), env)
        target = env['target']
        def trace(frame, event, arg):
            if frame.f_code is target.__code__ and event == 'line' and frame.f_lineno == 3:
                self.assertIsNone(native.jump(frame, 4))
            return trace
        previous = sys.gettrace()
        try:
            sys.settrace(trace)
            self.assertEqual(target(), 1)
        finally:
            sys.settrace(previous)

    def test_public_line_jump_rejects_outside_trace_and_into_except(self):
        self.assertEqual(native.jump(sys._getframe(), 1)[0], 7)
        source = 'def target():\n    x = 1\n    try:\n        x += 1\n    except ValueError:\n        x = 99\n    return x\n'
        env = {}
        exec(native.compile(source), env)
        target = env['target']
        rejected = []
        def trace(frame, event, arg):
            if frame.f_code is target.__code__ and event == 'line' and frame.f_lineno == 2:
                rejected.append(native.jump(frame, 6))
            return trace
        previous = sys.gettrace()
        try:
            sys.settrace(trace)
            self.assertEqual(target(), 2)
        finally:
            sys.settrace(previous)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0][0], 7)

    def test_diagnostics_use_live_frames(self):
        target = Path('/out/data/Runtime')
        target.mkdir(parents=True, exist_ok=True)
        native.dump_state()
        captures = list(target.glob('qualification_frame_state_*.dump'))
        self.assertTrue(captures)
        self.assertTrue(any('qualify_util.py' in f.read_text() for f in captures))
        self.assertTrue(all('Last line:' in f.read_text() for f in captures))

    def test_native_c_trace_line_jump(self):
        code = native.compile('value = 1\nvalue = 999\nresult = value\n')
        self.assertEqual(native.native_trace(code, 2, 3), (1, 1))

    def test_control_errors_preserve_native_flags(self):
        self.assertEqual(native.control(False), (True, True))
        self.assertEqual(native.control(True), (True, True))
        def user_error():
            raise RuntimeError('EXECUTION ABORTED')
        self.assertEqual(native.scope(user_error)[0], 8)

    def test_original_spell_driver_exception(self):
        original = Path('/source/src/spell/spell/lib/exception.py')
        spec = importlib.util.spec_from_file_location('spell.lib.exception', original)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        previous = sys.modules.get('spell.lib.exception')
        sys.modules['spell.lib.exception'] = module
        try:
            def fail():
                raise module.DriverException('original error', 'original reason')
            result = native.scope(fail)
            self.assertEqual(result[0], 9)
            self.assertIn('original error', result[1])
            self.assertEqual(result[2], 'original reason')
        finally:
            if previous is None: sys.modules.pop('spell.lib.exception')
            else: sys.modules['spell.lib.exception'] = previous


suite = unittest.defaultTestLoader.loadTestsFromTestCase(NativeUtil)
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = {'tests':result.testsRun, 'failures':len(result.failures), 'errors':len(result.errors),
          'skips':len(result.skipped), 'address_sanitizer':True, 'undefined_behavior_sanitizer':True,
          'leak_sanitizer':False, 'reference_lifetime_tests':True, 'full_spell_executor_qualified':False}
Path('/out/util-runtime.json').write_text(json.dumps(report, indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
