"""Experimental logical caller continuation, not the original executor integration.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest


class CallerRecovery(unittest.TestCase):
    def check_chain(self, source, subject, line, expected, occurrence=1):
        with tempfile.TemporaryDirectory(dir='/out') as directory:
            root = Path(directory)
            program = root/'procedure.py'
            program.write_text(source)
            command = [sys.executable, '-I', str(Path(__file__).with_name('persistent_worker.py'))]
            args = [str(program), str(root/'checkpoint.ws'), str(root/'result.json'), str(line), str(occurrence), subject]
            captured = subprocess.run(command+['capture-chain']+args, capture_output=True,text=True,timeout=15)
            self.assertEqual(captured.returncode, -signal.SIGKILL, captured.stderr)
            resumed = subprocess.run(command+['resume']+args,capture_output=True,text=True,timeout=15)
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertEqual(json.loads((root/'result.json').read_text())['result'], expected)

    def test_callee_return_flows_into_caller_expression(self):
        self.check_chain('def child(x):\n value=x*2\n return value\ndef parent(x):\n return 100+child(x)+1\nresult=parent(7)\n', 'child', 3, 115)

    def test_recursive_callers_and_multiple_operand_values(self):
        self.check_chain('def run(n):\n if n==0:\n  return 1\n return n*run(n-1)+n\nresult=run(4)\n', 'run', 3, 88)

    def test_function_argument_kinds(self):
        self.check_chain('def child(a, /, b=2, *args, scale=3, **kw):\n total=(a+b+sum(args)+kw["extra"])*scale\n return total\nresult=child(1,4,5,6,scale=2,extra=7)\n', 'child', 3, 46)

    def test_closure_cell_shared_with_caller(self):
        self.check_chain('def outer():\n value=9\n def child():\n  nonlocal value\n  value+=1\n  return value\n answer=child()\n return answer+value\nresult=outer()\n', 'child', 5, 20)

    def test_child_and_parent_have_distinct_handled_exceptions(self):
        self.check_chain('def child():\n try:\n  raise ValueError("child")\n except ValueError:\n  value=1\n return value\ntry:\n raise KeyError("parent")\nexcept KeyError:\n child()\n try:\n  raise\n except KeyError as error:\n  result=str(error)\n', 'child', 5, "'parent'")

    def test_new_child_exception_enters_parent_handler_and_finally(self):
        self.check_chain('def child():\n value=1\n raise ValueError("resumed")\ndef parent():\n try:\n  child()\n except ValueError as error:\n  return str(error)\n finally:\n  events.append("finally")\nevents=[]\nresult=(parent(),events)\n', 'child', 3, ['resumed',['finally']])

    def test_new_child_exception_propagates_through_multiple_callers(self):
        self.check_chain('def child():\n value=1\n raise KeyError("resumed")\ndef parent():\n return child()\ntry:\n parent()\nexcept KeyError as error:\n result=str(error)\n', 'child', 3, "'resumed'")

    def test_context_manager_exit_receives_resumed_exception(self):
        self.check_chain('class Context:\n def __enter__(self):\n  events.append("enter")\n def __exit__(self, *error):\n  events.append(str(error[1]))\n  return True\ndef child():\n value=1\n raise ValueError("suppressed")\nevents=[]\nwith Context():\n child()\nresult=events\n', 'child', 9, ['enter','suppressed'])

    def test_exception_group_handlers_receive_child_failure(self):
        self.check_chain('def child():\n value=1\n raise ExceptionGroup("group",[ValueError("value"),KeyError("key")])\nresult=[]\ntry:\n child()\nexcept* ValueError as group:\n result.append(str(group.exceptions[0]))\nexcept* KeyError as group:\n result.append(str(group.exceptions[0]))\n', 'child', 3, ['value',"'key'"])

    def test_c_call_boundary_is_rejected_before_checkpoint_publication(self):
        with tempfile.TemporaryDirectory(dir='/out') as directory:
            root=Path(directory)
            program=root/'procedure.py'
            program.write_text('def child(value):\n result=value*2\n return result\nresult=sorted([1,2],key=child)\n')
            result=subprocess.run([sys.executable,'-I',str(Path(__file__).with_name('persistent_worker.py')),
                'capture-chain',str(program),str(root/'checkpoint.ws'),str(root/'result.json'),'2','1','child'],
                capture_output=True,text=True,timeout=15)
            self.assertNotEqual(result.returncode,0)
            self.assertNotEqual(result.returncode,-signal.SIGKILL)
            self.assertIn('C-call boundary',result.stderr)
            self.assertFalse((root/'checkpoint.ws').exists())

    def test_generator_and_excessive_depth_fail_before_publication(self):
        cases = [('def gen():\n yield 1\nresult=list(gen())\n', 'gen', 2, 'synchronous thread-owned'),
                 ('def run(n):\n if n==0:\n  return 1\n return run(n-1)\nresult=run(130)\n', 'run', 3, '128 caller frames')]
        for source, subject, line, message in cases:
            with self.subTest(subject=subject), tempfile.TemporaryDirectory(dir='/out') as directory:
                root=Path(directory)
                program=root/'procedure.py'
                program.write_text(source)
                result=subprocess.run([sys.executable,'-I',str(Path(__file__).with_name('persistent_worker.py')),
                    'capture-chain',str(program),str(root/'checkpoint.ws'),str(root/'result.json'),str(line),'1',subject],
                    capture_output=True,text=True,timeout=15)
                self.assertNotEqual(result.returncode,0)
                self.assertNotEqual(result.returncode,-signal.SIGKILL)
                self.assertIn(message,result.stderr)
                self.assertFalse((root/'checkpoint.ws').exists())


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CallerRecovery))
Path('/out/chain-probe.json').write_text(json.dumps({'experiment_only':True,
    'full_spell_warm_start_qualified':False, 'tests':result.testsRun,
    'failures':len(result.failures), 'errors':len(result.errors), 'skips':len(result.skipped),
    'logical_caller_continuation':True, 'physical_python_caller_chain_restored':False,
    'address_sanitizer':True, 'undefined_behavior_sanitizer':True, 'leak_sanitizer':False,
}, indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
