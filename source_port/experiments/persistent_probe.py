"""Fresh-process, real-storage recovery checks. SPDX-License-Identifier: GPL-3.0-or-later."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from persistent_codec import identity, load, probe, save, storage


class PersistentRecovery(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir='/out')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root/'procedure.py'
        self.checkpoint = self.root/'state.ws'
        self.result = self.root/'result.json'

    def worker(self, mode, line=1, occurrence=1, subject='<module>'):
        return subprocess.run([sys.executable, '-I', str(Path(__file__).with_name('persistent_worker.py')),
            mode, str(self.source), str(self.checkpoint), str(self.result), str(line), str(occurrence), subject],
            capture_output=True, text=True, timeout=15)

    def crash_resume(self, source, line, occurrence=1, subject='<module>'):
        self.source.write_text(source)
        capture = self.worker('capture', line, occurrence, subject)
        self.assertEqual(capture.returncode, -signal.SIGKILL, capture.stderr)
        self.assertTrue(self.checkpoint.is_file())
        resumed = self.worker('resume')
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        return json.loads(self.result.read_text())

    def test_killed_process_resumes_loop_without_replaying_external_prefix(self):
        effects = self.root/'effects'
        source = f"from pathlib import Path\np = Path({str(effects)!r})\np.write_text(p.read_text()+'prefix\\n' if p.exists() else 'prefix\\n')\ntotal=0\nfor i in range(8):\n total+=i\nresult=total\n"
        result = self.crash_resume(source, 6, occurrence=5)
        self.assertEqual(result['result'], 28)
        self.assertEqual(effects.read_text(), 'prefix\n')

    def test_crash_does_not_execute_finally_until_resume(self):
        effect = self.root/'finally'
        source = f"from pathlib import Path\ntry:\n value=17\n result=value+4\nfinally:\n p=Path({str(effect)!r})\n p.write_text(p.read_text()+'done\\n' if p.exists() else 'done\\n')\n"
        self.source.write_text(source)
        captured = self.worker('capture', 4)
        self.assertEqual(captured.returncode, -signal.SIGKILL, captured.stderr)
        self.assertFalse(effect.exists())
        resumed = self.worker('resume')
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(effect.read_text(), 'done\n')
        self.assertEqual(json.loads(self.result.read_text())['result'], 21)

    def test_function_locals_and_operand_stack_in_fresh_process(self):
        source = 'def run():\n total=0\n for item in [2,4,8,16]:\n  total+=item\n return total\nresult=run()\n'
        result = self.crash_resume(source, 4, occurrence=3, subject='run')
        self.assertEqual(result['return'], 30)

    def test_cycles_and_shared_aliases_across_namespace_and_stack(self):
        source = 'items=[1,2,3]\nalias=items\ncycle=[]\ncycle.append(cycle)\nfor item in items:\n alias.append(4) if len(alias)==3 else None\n result=(items is alias, cycle[0] is cycle, sum(items))\n'
        result = self.crash_resume(source, 6, occurrence=2)
        self.assertEqual(result['result'], [True, True, 10])

    def test_saved_exception_can_be_reraised_after_process_death(self):
        source = "try:\n raise ValueError('saved')\nexcept ValueError:\n result='caught'\n try:\n  raise\n except ValueError as error:\n  result+=':'+str(error)\nfinally:\n result+=':finally'\n"
        result = self.crash_resume(source, 4)
        self.assertEqual(result['result'], 'caught:saved:finally')

    def test_changed_source_is_rejected_before_continuation(self):
        self.source.write_text('value=1\nresult=value+2\n')
        captured = self.worker('capture', 2)
        self.assertEqual(captured.returncode, -signal.SIGKILL, captured.stderr)
        self.source.write_text('value=999\nresult=value+2\n')
        resumed = self.worker('resume')
        self.assertNotEqual(resumed.returncode, 0)
        self.assertIn('identity mismatch', resumed.stderr)
        self.assertFalse(self.result.exists())

    def test_exception_cause_context_notes_and_identity_survive(self):
        source = "import sys\ntry:\n try:\n  raise ValueError('inner')\n except ValueError as inner:\n  raise RuntimeError('outer') from inner\nexcept RuntimeError as error:\n error.add_note('note')\n current=sys.exception()\n result=(str(current.__cause__), str(current.__context__), current.__cause__ is current.__context__, current.__suppress_context__, current.__notes__)\n"
        result = self.crash_resume(source, 9)
        self.assertEqual(result['result'], ['inner', 'inner', True, True, ['note']])

    def test_dynamic_function_reads_updated_module_global(self):
        source = 'value=3\ndef read():\n return value\nvalue=9\nresult=read()\n'
        result = self.crash_resume(source, 4)
        self.assertEqual(result['result'], 9)

    def test_mutual_recursion_function_alias_and_global_namespace_identity(self):
        source = 'value=2\ndef even(n):\n return odd(n-1) if n else value\ndef odd(n):\n return even(n-1) if n else value+1\nalias=[even,even]\nvalue=10\nresult=(even(4),odd(4),alias[0] is alias[1],even.__globals__ is globals(),odd.__globals__ is globals())\n'
        result = self.crash_resume(source, 7)
        self.assertEqual(result['result'], [10,11,True,True,True])

    def test_runtime_and_payload_mismatch_are_rejected_before_unpickling(self):
        for mismatch in ('python', 'payload_sha256'):
            writer = storage.create(str(self.checkpoint), 1)
            metadata = identity(b'pass') | {'payload_sha256':'0'*64}
            if mismatch == 'python':
                metadata['python'] = 'different build'
            storage.store(writer, metadata)
            storage.store(writer, b'not a pickle')
            del writer
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                load(self.checkpoint, b'pass')

    def test_failed_atomic_commit_retains_previous_checkpoint(self):
        code = compile('pass', '<atomic>', 'exec')
        state = (code, {}, {}, None, (), b'', 0)
        save(self.checkpoint, b'pass', state)
        original = self.checkpoint.read_bytes()
        with self.assertRaisesRegex(OSError, 'before commit'):
            save(self.checkpoint, b'pass', state, fail_before_replace=True)
        self.assertEqual(self.checkpoint.read_bytes(), original)
        self.assertEqual(list(self.root.glob('state.ws.*')), [])

    def test_native_state_extent_and_null_flags_rejected(self):
        code = compile('pass', '<invalid>', 'exec')
        for state in ((code, {}, {}, None, (), b'', 99999),
                      (code, {}, {}, None, (None,), b'\x02', 0),
                      (code, {}, {}, None, (), b'\x00', 0)):
            with self.assertRaises(ValueError):
                probe.from_state(state)

    def test_live_file_resources_are_rejected(self):
        code = compile('pass', '<resource>', 'exec')
        with open(self.root/'live', 'w') as handle:
            with self.assertRaisesRegex(TypeError, 'external resources'):
                save(self.checkpoint, b'pass', (code, {'nested':[handle]}, {}, None, (), b'', 0))
        self.assertFalse(self.checkpoint.exists())


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PersistentRecovery))
Path('/out/persistent-probe.json').write_text(json.dumps({
    'experiment_only':True, 'full_spell_warm_start_qualified':False,
    'tests':result.testsRun, 'failures':len(result.failures), 'errors':len(result.errors),
    'skips':len(result.skipped), 'real_spell_ws_storage':True,
    'sigkill_then_fresh_process':True, 'single_frame_only':True,
    'address_sanitizer':True, 'undefined_behavior_sanitizer':True, 'leak_sanitizer':False,
}, indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
