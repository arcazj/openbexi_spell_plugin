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


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Feasibility))
Path('/out/recovery-probe.json').write_text(json.dumps({
    'experiment_only':True, 'full_spell_warm_start_qualified':False,
    'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
    'skips':len(result.skipped), 'persistent_serialization':False, 'nested_call_chain':False,
    'address_sanitizer':True, 'undefined_behavior_sanitizer':True, 'leak_sanitizer':False,
}, indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
