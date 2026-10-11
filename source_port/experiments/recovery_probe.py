"""Single-frame recovery feasibility, not full SPELL qualification. SPDX-License-Identifier: GPL-3.0-or-later."""
import gc
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

spec = importlib.util.spec_from_file_location('_recovery_probe', next(Path('/out').glob('_recovery_probe*.so')))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Feasibility(unittest.TestCase):
    def snapshot(self, source, line, occurrence=1, function=False):
        program = compile(source, 'checkpoint.py', 'exec')
        subject = next(c for c in program.co_consts if isinstance(c, types.CodeType)) if function else program
        return probe.capture(program, subject, {}, line, occurrence)

    def test_module_resume_does_not_repeat_prefix(self):
        snapshot = self.snapshot('value = 7\nvalue += 3\nresult = value\n', 3)
        result, globals, offset, slots = probe.resume(snapshot)
        self.assertIsNone(result)
        self.assertEqual(globals['result'], 10)
        self.assertGreater(offset, 0)

    def test_loop_operand_stack_and_iterator_position(self):
        snapshot = self.snapshot('total = 0\nfor i in range(5):\n total += i\nresult = total\n', 3, occurrence=3)
        _, globals, _, slots = probe.resume(snapshot)
        self.assertEqual(globals['result'], 10)
        self.assertGreater(slots, 0)

    def test_function_fast_locals_and_return_value(self):
        snapshot = self.snapshot('def run():\n total = 0\n for i in range(5):\n  total += i\n return total\nresult = run()\n', 4, occurrence=3, function=True)
        result, _, _, slots = probe.resume(snapshot)
        self.assertEqual(result, 10)
        self.assertGreater(slots, 2)

    def test_active_exception_state_and_finally(self):
        snapshot = self.snapshot("result = ''\ntry:\n raise ValueError('saved')\nexcept ValueError:\n result = 'handler'\n try:\n  raise\n except ValueError as error:\n  result += ':' + str(error)\nfinally:\n result += ':finally'\n", 5)
        _, globals, _, _ = probe.resume(snapshot)
        self.assertEqual(globals['result'], 'handler:saved:finally')
        self.assertIsNone(sys.exception())

    def test_reference_cycles_and_repeated_recovery(self):
        for _ in range(200):
            snapshot = self.snapshot('def run():\n value = [1,2,3]\n return value\nresult = run()\n', 3, function=True)
            self.assertEqual(probe.resume(snapshot)[0], [1,2,3])
            del snapshot
        gc.collect()
        self.assertIsNone(sys.gettrace())

    def test_missing_checkpoint_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'not reached'):
            self.snapshot('pass\n', 100)
        self.assertIsNone(sys.gettrace())

    def test_existing_trace_is_restored_on_success_and_failure(self):
        events = []
        def tracing(frame, event, value):
            events.append(event)
            return tracing
        sys.settrace(tracing)
        try:
            snapshot = self.snapshot('value=1\nresult=value+1\n', 2)
            self.assertIs(sys.gettrace(), tracing)
            self.assertEqual(probe.resume(snapshot)[1]['result'], 2)
            self.assertIs(sys.gettrace(), tracing)
            with self.assertRaises(RuntimeError):
                self.snapshot('pass', 100)
            self.assertIs(sys.gettrace(), tracing)
        finally:
            sys.settrace(None)
        self.assertTrue(events)

    def test_state_loader_rejects_non_tuple(self):
        with self.assertRaises(TypeError):
            probe.from_state(None)

    def test_function_positional_keyword_variadic_and_default_arguments(self):
        source = 'def run(a, /, b=2, *rest, scale=3, **options):\n total=(a+b+sum(rest)+options["extra"])*scale\n return total\nresult=run(1,4,5,6,scale=2,extra=7)\n'
        snapshot = self.snapshot(source, 2, function=True)
        self.assertEqual(probe.resume(snapshot)[0], 46)

    def test_shared_closure_cell_survives_resumption(self):
        source = 'def outer():\n value=9\n def run():\n  nonlocal value\n  value+=1\n  return value\n return run()\nresult=outer()\n'
        program = compile(source, 'closure.py', 'exec')
        outer = next(c for c in program.co_consts if isinstance(c, types.CodeType))
        inner = next(c for c in outer.co_consts if isinstance(c, types.CodeType))
        snapshot = probe.capture(program, inner, {}, 5)
        self.assertEqual(probe.resume(snapshot)[0], 10)

    def test_resumed_dispatch_sees_restored_state_and_live_edits(self):
        snapshot = self.snapshot('def run():\n value=7\n value+=3\n return value\nresult=run()\n', 4, function=True)
        events = []
        def tracing(frame, event, arg):
            if frame.f_code.co_filename == 'checkpoint.py':
                events.append((event, frame.f_lineno, dict(frame.f_locals)))
                if event == 'line': frame.f_locals['value'] = 42
            return tracing
        sys.settrace(tracing)
        try:
            self.assertEqual(probe.resume_traced(snapshot)[0], 42)
            self.assertIs(sys.gettrace(), tracing)
        finally:
            sys.settrace(None)
        self.assertEqual([event for event, _, _ in events], ['call','line','return'])
        self.assertEqual(events[0][1:], (4, {'value':10}))

    def test_resumed_dispatch_observes_nested_calls_and_exception_cleanup(self):
        source = 'def child():\n raise ValueError("after restore")\ndef run():\n events=[]\n try:\n  child()\n finally:\n  events.append("finally")\nrun()\n'
        program = compile(source, 'checkpoint.py', 'exec')
        subject = next(c for c in program.co_consts if isinstance(c, types.CodeType) and c.co_name == 'run')
        # Capture before entering try: this in-memory probe stops by unwinding,
        # which otherwise mutates the shared list in the original finally.
        # Persistence tests capture and SIGKILL before any unwind.
        snapshot = probe.capture(program, subject, {}, 5)
        events = []
        def tracing(frame, event, arg):
            if frame.f_code.co_filename == 'checkpoint.py':
                events.append((frame.f_code.co_name, event, dict(frame.f_locals)))
            return tracing
        sys.settrace(tracing)
        try:
            with self.assertRaisesRegex(ValueError, 'after restore'): probe.resume_traced(snapshot)
            self.assertIs(sys.gettrace(), tracing)
        finally:
            sys.settrace(None)
        self.assertIn(('child', 'call'), [(name,event) for name,event,_ in events])
        self.assertEqual(events[-1], ('run','return', {'events':['finally']}))

    def test_recheckpoint_resumed_live_frame(self):
        snapshot = self.snapshot('value=7\nvalue+=3\nresult=value\n', 2)
        saved = []
        def tracing(frame, event, arg):
            if frame.f_code.co_filename == 'checkpoint.py' and event == 'line' and frame.f_lineno == 3:
                saved.append(probe.snapshot(frame, sys.exception()))
            return tracing
        sys.settrace(tracing)
        try: self.assertEqual(probe.resume_traced(snapshot)[1]['result'], 10)
        finally: sys.settrace(None)
        self.assertEqual(len(saved), 1)
        view = probe.inspection(saved[0])
        self.assertEqual(view.f_lineno, 3)
        self.assertEqual(view.f_globals['value'], 10)
        self.assertEqual(probe.resume(probe.from_state(saved[0]))[1]['result'], 10)

    def test_dispatch_failure_restores_previous_trace(self):
        snapshot = self.snapshot('value=1\nresult=value\n', 2)
        def tracing(frame, event, arg):
            if frame.f_code.co_filename == 'checkpoint.py': raise LookupError('dispatch failed')
            return tracing
        sys.settrace(tracing)
        try:
            with self.assertRaisesRegex(LookupError, 'dispatch failed'): probe.resume_traced(snapshot)
            self.assertIs(sys.gettrace(), tracing)
        finally: sys.settrace(None)


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Feasibility))
Path('/out/recovery-probe.json').write_text(json.dumps({
    'experiment_only':True, 'full_spell_warm_start_qualified':False,
    'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
    'skips':len(result.skipped), 'persistent_serialization':False, 'nested_call_chain':False,
    'address_sanitizer':True, 'undefined_behavior_sanitizer':True, 'leak_sanitizer':False,
}, indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
