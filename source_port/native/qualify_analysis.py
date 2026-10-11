"""Independent original EXC analyzer checks. SPDX-License-Identifier: GPL-3.0-or-later."""
import dis
import gc
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import textwrap
import types
import unittest
import weakref

extension = next(Path('/out').glob('_spell_analysis_qualification*.so'))
spec = importlib.util.spec_from_file_location('_spell_analysis_qualification', extension)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeAnalysis(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.file = Path(self.directory.name) / 'procedure_通信.py'
        self.analyzer = native.create()

    def parse(self, source):
        self.file.write_text(source, encoding='utf-8')
        native.process(self.analyzer, str(self.file))

    def kinds(self, count):
        result = []
        for line in range(1, count + 1):
            simple, start, inside, _ = native.classify(self.analyzer, line)
            self.assertEqual(simple + start + inside, 1)
            result.append('S' if simple else 'B' if start else 'I')
        return ''.join(result)

    def assert_lines(self, code):
        starts = [(offset, line) for offset, line in dis.findlinestarts(code) if line is not None and line > 0]
        result = native.lines(code)
        self.assertEqual([r[0] for r in result['rows']], [line for _, line in starts])
        self.assertEqual(result['first'], starts[0][1] if starts else -1)
        self.assertEqual(result['missing'], (-1, -1, -1))
        for line, before, after, offset, mapped in result['rows']:
            i = next(i for i, (_, n) in enumerate(starts) if n == line)
            self.assertEqual(before, starts[i - 1][1] if i else line)
            self.assertEqual(after, starts[i + 1][1] if i + 1 < len(starts) else -1)
            self.assertEqual(offset, starts[i][0])
            self.assertEqual(mapped, line)
        return result

    def test_single_line_brackets_strings_and_comments(self):
        self.parse('x = [1, (2, 3), {4: 5}]\ny = "([)]"\n# [ ( {\nz = 4\n')
        self.assertEqual(self.kinds(4), 'SSSS')

    def test_nested_multiline_and_next_statement(self):
        self.parse('x = [\n    (1,\n     2),\n    {3: 4}\n]\ny = 9\n')
        self.assertEqual(self.kinds(6), 'BIIIIS')
        self.assertEqual(native.classify(self.analyzer, 1)[3], 6)

    def test_blank_and_comment_lines_inside_continuation(self):
        self.parse('x = (\n\n# comment with )\n  3\n)\ny = 4\n')
        self.assertEqual(self.kinds(6), 'BIIIIS')

    def test_independent_multiline_expressions(self):
        self.parse('x = (\n 1\n)\ny = [\n 2\n]\nz = 3\n')
        self.assertEqual(self.kinds(7), 'BIIBIIS')
        self.assertEqual(native.classify(self.analyzer, 1)[3], 4)
        self.assertEqual(native.classify(self.analyzer, 4)[3], 7)

    def test_strings_do_not_supply_delimiters(self):
        self.parse('x = """[\n (\n ]"""\ny = "通信 )"\nz = f"value {3}"\n')
        self.assertEqual(self.kinds(5), 'SSSSS')

    def test_multiline_fstring_expression(self):
        self.parse('x = f"value {sum([\n1, 2\n])}"\ny = 3\n')
        self.assertEqual(self.kinds(4), 'BIIS')

    def test_reparse_same_filename_after_edit(self):
        self.parse('x = (\n 1\n)\n')
        self.assertEqual(self.kinds(3), 'BII')
        self.parse('x = 1\ny = 2\nz = 3\n')
        self.assertEqual(self.kinds(3), 'SSS')

    def test_invalid_parse_clears_previous_result_and_recovers(self):
        self.parse('x = (\n 1\n)\n')
        with self.assertRaises(RuntimeError): self.parse('if True\n broken\n')
        self.assertEqual(self.kinds(3), 'SSS')
        self.parse('x = [\n2\n]\n')
        self.assertEqual(self.kinds(3), 'BII')

    def test_missing_file_and_null_source(self):
        with self.assertRaises(RuntimeError): native.process(self.analyzer, str(self.file))
        with self.assertRaises(RuntimeError): self.parse('x = 1\0bad')
        self.parse('x = 3\n')
        self.assertEqual(self.kinds(1), 'S')

    def test_initial_and_outside_lines_are_safe(self):
        self.assertEqual(self.kinds(3), 'SSS')
        self.parse('pass\n')
        self.assertEqual(native.classify(self.analyzer, 100), (1, 0, 0, 100))

    def test_line_table_ordinary_nested_code(self):
        code = compile('x = 1\ndef f(value):\n    return [i*i for i in range(value)]\ny = f(3)\n', 'lines.py', 'exec')
        self.assert_lines(code)
        for child in code.co_consts:
            if isinstance(child, types.CodeType): self.assert_lines(child)

    def test_line_table_backward_lines_and_handlers(self):
        code = compile(textwrap.dedent('''\
            def run():
                result = []
                for i in range(3):
                    try:
                        result.append(10 // i)
                    except ZeroDivisionError:
                        result.append(-1)
                    finally:
                        result.append(i)
                return result
            '''), 'handlers.py', 'exec')
        child = next(c for c in code.co_consts if isinstance(c, types.CodeType))
        table = self.assert_lines(child)
        self.assertTrue(any(b[0] < a[0] for a, b in zip(table['rows'], table['rows'][1:])))
        namespace = {}
        exec(code, namespace)
        seen = []
        def trace(frame, event, arg):
            if event == 'line' and frame.f_code is child: seen.append(frame.f_lineno)
            return trace
        previous = sys.gettrace()
        try:
            sys.settrace(trace)
            self.assertEqual(namespace['run'](), [-1, 0, 10, 1, 5, 2])
        finally:
            sys.settrace(previous)
        self.assertTrue(set(seen).issubset({r[0] for r in table['rows']}))

    def test_line_table_large_offsets_and_line_deltas(self):
        source = '\n'.join(f'value_{i} = {i}' for i in range(400)) + '\n' * 350 + 'result = value_399\n'
        table = self.assert_lines(compile(source, 'large.py', 'exec'))
        self.assertGreater(table['rows'][-1][3], 1000)
        self.assertGreater(table['rows'][-1][0], 700)

    def test_line_table_empty_and_generated_code(self):
        self.assert_lines(compile('', 'empty.py', 'exec'))
        self.assert_lines(compile('42', 'expression.py', 'eval'))
        with self.assertRaises(TypeError): native.lines('not code')

    def test_analyzer_reference_ownership(self):
        code = compile('x = 1\ny = x + 2\n', 'ownership.py', 'exec')
        native.lines(code)
        before = sys.getrefcount(code)
        for _ in range(2000): native.lines(code)
        gc.collect()
        self.assertEqual(sys.getrefcount(code), before)
        self.file.write_text('value = [\n  1, 2\n]\n', encoding='utf-8')
        for _ in range(200):
            analyzer = native.create()
            native.process(analyzer, str(self.file))
            self.assertEqual(native.classify(analyzer, 2)[:3], (0, 0, 1))

    def goto(self, source):
        return native.goto_info(compile(source, 'goto.py', 'exec'), len(source.splitlines()))

    def test_goto_static_labels_init_and_forward_target(self):
        result = self.goto("Step('INIT', 'start')\nGoto('END')\nStep('END', 'done')\n")
        self.assertEqual(result['labels'], {'INIT': 1, 'END': 3})
        self.assertEqual(result['rows'], [(1, 1, 1, -1), (2, 0, 0, 3), (3, 1, 0, -1)])
        self.assertEqual(result['missing'], '')
        self.assertTrue(result['init'])

    def test_goto_multiline_and_unicode(self):
        result = self.goto("Step(\n '通信',\n 'description'\n)\nGoto(\n '通信'\n)\n")
        self.assertEqual(result['labels'], {'通信': 1})
        self.assertEqual(result['rows'][4][3], 1)
        self.assertFalse(result['init'])

    def test_goto_unknown_target_is_safe(self):
        result = self.goto("Goto('MISSING')\nStep('FOUND', 'here')\n")
        self.assertEqual(result['missing'], 'MISSING')
        self.assertEqual(result['rows'][0][3], -1)

    def test_goto_function_scope_load_global(self):
        code = compile("def child():\n Step('INNER', 'inside')\n Goto('INNER')\nStep('OUTER', 'outside')\n", 'scopes.py', 'exec')
        self.assertEqual(native.goto_info(code, 4)['labels'], {'OUTER': 4})
        child = next(c for c in code.co_consts if isinstance(c, types.CodeType))
        result = native.goto_info(child, 4)
        self.assertEqual(result['labels'], {'INNER': 2})
        self.assertEqual(result['rows'][2][3], 2)

    def test_goto_extended_operands_and_inline_caches(self):
        prefix = '\n'.join(f'name_{n} = {n}' for n in range(350)) + '\n'
        result = self.goto(prefix + "Step('LATE', 'late')\nGoto('LATE')\n")
        self.assertEqual(result['labels'], {'LATE': 351})
        self.assertEqual(result['rows'][351][3], 351)

    def test_goto_does_not_fabricate_dynamic_or_unrelated_labels(self):
        result = self.goto("Step('VALID', 'ok')\nStep(value, 'not an id')\nStep('prefix' + value, 'not literal')\nStep(None, 'not an id')\nStep('one argument')\nStep\nother('STALE', 'not a label')\nGoto(target)\n")
        self.assertEqual(result['labels'], {'VALID': 1})
        self.assertEqual(result['missing'], '')

    def test_goto_keeps_legacy_first_duplicate_target(self):
        result = self.goto("Step('SAME', 'first')\nStep('SAME', 'second')\nGoto('SAME')\n")
        self.assertEqual(result['labels'], {'SAME': 1})
        self.assertEqual(result['rows'][2][3], 1)

    def test_goto_reference_ownership(self):
        code = compile("Step('A', 'a')\nGoto('A')\n", 'ownership.py', 'exec')
        native.goto_info(code, 2)
        before = sys.getrefcount(code)
        for _ in range(2000): native.goto_info(code, 2)
        gc.collect()
        self.assertEqual(sys.getrefcount(code), before)

    def test_goto_analysis_drives_actual_forward_c_trace_jump(self):
        # Step is a recording fixture, not the unreleased native Step binding.
        stages, events = [], []
        namespace = {'Step': lambda *args: stages.append(args), 'events': events}
        code = compile("Step('INIT','start')\nevents.append('before')\nGoto('END')\nevents.append('skipped')\nStep('END','done')\nevents.append('after')\n", 'forward.py', 'exec')
        self.assertEqual(native.goto_trace(code, namespace), 1)
        self.assertEqual(events, ['before', 'after'])
        self.assertEqual(stages, [('INIT', 'start'), ('END', 'done')])

    def test_goto_analysis_drives_actual_backward_c_trace_jump(self):
        stages = []
        namespace = {'Step': lambda *args: stages.append(args)}
        code = compile("count = 0\nStep('AGAIN','loop')\ncount += 1\nif count < 3:\n Goto('AGAIN')\nresult = count\n", 'backward.py', 'exec')
        self.assertEqual(native.goto_trace(code, namespace), 2)
        self.assertEqual(namespace['result'], 3)
        self.assertEqual(stages, [('AGAIN', 'loop')] * 3)

    def test_goto_c_trace_rejects_illegal_handler_entry(self):
        code = compile("Goto('HANDLER')\ntry:\n 1 / 0\nexcept ZeroDivisionError:\n Step('HANDLER','forbidden entry')\n", 'forbidden.py', 'exec')
        with self.assertRaisesRegex(RuntimeError, 'except'):
            native.goto_trace(code, {})
        self.assertIsNone(sys.gettrace())

    def test_watch_reads_live_function_locals(self):
        value = 41
        handle = native.watch_create(sys._getframe(), ['handle','self'])
        try:
            self.assertEqual(native.watch_state(handle)['locals']['value']['value'], '41')
            self.assertFalse(native.watch_get(handle, 'value')['global'])
        finally: native.watch_close(handle)

    def test_watch_local_write_changes_running_function(self):
        value = 41
        handle = native.watch_create(sys._getframe(), ['handle','self'])
        try:
            native.watch_change(handle, 'value', 'value + 1', False)
            self.assertEqual(value, 42)
            self.assertEqual(native.watch_get(handle, 'value')['value'], '42')
        finally: native.watch_close(handle)

    def test_watch_closure_cell_is_readable_and_writable(self):
        value = 3
        def inner():
            _ = value
            handle = native.watch_create(sys._getframe(), ['handle','self'])
            try:
                self.assertEqual(native.watch_get(handle, 'value')['value'], '3')
                native.watch_change(handle, 'value', '8', False)
                return value
            finally: native.watch_close(handle)
        self.assertEqual(inner(), 8)
        self.assertEqual(value, 8)

    def test_watch_shadowed_global_and_local_remain_distinct(self):
        globals()['WATCH_SHADOW'] = 100
        WATCH_SHADOW = 2
        handle = native.watch_create(sys._getframe(), ['handle','self'])
        try:
            state = native.watch_state(handle)
            self.assertEqual(state['globals']['WATCH_SHADOW']['value'], '100')
            self.assertEqual(state['locals']['WATCH_SHADOW']['value'], '2')
            self.assertFalse(native.watch_get(handle, 'WATCH_SHADOW')['global'])
            native.watch_change(handle, 'WATCH_SHADOW', '200', True)
            self.assertEqual(WATCH_SHADOW, 2)
            self.assertEqual(globals()['WATCH_SHADOW'], 200)
        finally:
            native.watch_close(handle)
            globals().pop('WATCH_SHADOW')

    def test_watch_reports_add_change_delete(self):
        value = 1
        handle = native.watch_create(sys._getframe(), ['handle','self','events','rows'])
        try:
            value = 2
            added_value = 'new'
            native.watch_analyze(handle)
            events = native.watch_events(handle)
            rows = [row for event in events for row in event[0]]
            self.assertTrue(any(row['name'] == 'added_value' and row['added'] for row in rows))
            rows = [row for event in events for row in event[1]]
            self.assertTrue(any(row['name'] == 'value' and row['value'] == '2' for row in rows))
            del added_value
            native.watch_analyze(handle)
            rows = [row for event in native.watch_events(handle) for row in event[2]]
            self.assertTrue(any(row['name'] == 'added_value' and row['deleted'] for row in rows))
        finally: native.watch_close(handle)

    def test_watch_type_change_with_same_repr_is_reported(self):
        class First:
            def __repr__(self): return 'same'
        class Second:
            def __repr__(self): return 'same'
        value = First()
        handle = native.watch_create(sys._getframe(), ['handle','self','changes'])
        try:
            value = Second()
            native.watch_analyze(handle)
            changes = [row for event in native.watch_events(handle) for row in event[1]]
            self.assertTrue(any(row['name'] == 'value' and 'Second' in row['type'] for row in changes))
        finally: native.watch_close(handle)

    def test_watch_ignores_internal_initial_and_callable_variables(self):
        ignored = 12
        __internal = 3
        callable_value = lambda: None
        SCDB = {'system':'database'}
        handle = native.watch_create(sys._getframe(), ['handle','self','ignored'])
        try:
            local = native.watch_state(handle)['locals']
            for name in ['ignored','__internal','callable_value','SCDB']: self.assertNotIn(name, local)
        finally: native.watch_close(handle)

    def test_watch_preserves_quote_expressions_unicode_and_empty(self):
        通信 = 'before'
        handle = native.watch_create(sys._getframe(), ['handle','self'])
        try:
            native.watch_change(handle, '通信', repr('He said "hello"'), False)
            self.assertEqual(通信, 'He said "hello"')
            native.watch_change(handle, '通信', '<empty>', False)
            self.assertEqual(通信, '')
            self.assertEqual(native.watch_get(handle, '通信')['value'], "''")
        finally: native.watch_close(handle)

    def test_watch_failed_expression_preserves_value_and_recovers(self):
        value = 1
        handle = native.watch_create(sys._getframe(), ['handle','self'])
        try:
            with self.assertRaises(RuntimeError): native.watch_change(handle, 'value', '(', False)
            self.assertEqual(value, 1)
            with self.assertRaises(RuntimeError): native.watch_change(handle, 'not a name', '9', False)
            native.watch_change(handle, 'value', '7', False)
            self.assertEqual(value, 7)
        finally: native.watch_close(handle)

    def test_watch_failing_repr_does_not_break_monitor(self):
        class Unprintable:
            def __repr__(self): raise ValueError('cannot display')
        value = Unprintable()
        handle = native.watch_create(sys._getframe(), ['handle','self'])
        try:
            self.assertEqual(native.watch_get(handle, 'value')['value'], '<unprintable>')
            value = 9
            native.watch_analyze(handle)
            self.assertEqual(native.watch_get(handle, 'value')['value'], '9')
        finally: native.watch_close(handle)

    def test_watch_module_has_no_duplicate_locals(self):
        namespace = {'native': native, 'sys': sys}
        exec("value = 1\nhandle = native.watch_create(sys._getframe(), ['handle'])\ntry:\n snapshot = native.watch_state(handle)\nfinally:\n native.watch_close(handle)\n", namespace)
        self.assertEqual(namespace['snapshot']['locals'], {})
        self.assertEqual(namespace['snapshot']['globals']['value']['value'], '1')

    def test_watch_global_reference_is_borrowed_without_leak(self):
        payload = object()
        globals()['WATCH_PAYLOAD'] = payload
        handle = native.watch_create(sys._getframe(), ['handle','self'])
        try:
            before = sys.getrefcount(payload)
            for _ in range(2000): self.assertIs(native.watch_ref(handle, 'WATCH_PAYLOAD'), payload)
            self.assertEqual(sys.getrefcount(payload), before)
            self.assertIs(native.watch_ref(handle, 'len'), len)
            self.assertIsNone(native.watch_ref(handle, 'MISSING_GLOBAL_NAME'))
        finally:
            native.watch_close(handle)
            globals().pop('WATCH_PAYLOAD')

    def test_watch_close_releases_frames_and_values(self):
        refs = []
        class Payload: pass
        def exercise():
            value = Payload()
            refs.append(weakref.ref(value))
            handle = native.watch_create(sys._getframe(), ['handle','self'])
            native.watch_close(handle)
            native.watch_close(handle)
            with self.assertRaisesRegex(RuntimeError, 'closed'): native.watch_state(handle)
        for _ in range(200): exercise()
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))

    def test_watch_does_not_import_driver_framework(self):
        self.assertNotIn('spell.lib.adapter.databases.database', sys.modules)
        handle = native.watch_create(sys._getframe(), ['handle','self'])
        native.watch_close(handle)
        self.assertNotIn('spell.lib.adapter.databases.database', sys.modules)

    def test_watch_unchanged_values_do_not_notify(self):
        value = 1
        handle = native.watch_create(sys._getframe(), ['handle','self'])
        try:
            native.watch_analyze(handle)
            self.assertEqual(native.watch_events(handle), [])
        finally: native.watch_close(handle)

    def test_watch_newly_filtered_value_is_removed(self):
        value = 1
        handle = native.watch_create(sys._getframe(), ['handle','self','deleted'])
        try:
            value = lambda: None
            native.watch_analyze(handle)
            deleted = [row for event in native.watch_events(handle) for row in event[2]]
            self.assertTrue(any(row['name'] == 'value' for row in deleted))
            self.assertNotIn('value', native.watch_state(handle)['locals'])
        finally: native.watch_close(handle)

    def test_watch_repr_mutation_does_not_invalidate_iteration(self):
        class Mutator:
            def __repr__(self):
                globals().pop('WATCH_VICTIM', None)
                return 'stable'
        globals()['WATCH_MUTATOR'] = Mutator()
        globals()['WATCH_VICTIM'] = [1,2,3]
        handle = native.watch_create(sys._getframe(), ['handle','self'])
        try:
            native.watch_analyze(handle)
            self.assertEqual(native.watch_state(handle)['globals']['WATCH_MUTATOR']['value'], 'stable')
            self.assertNotIn('WATCH_VICTIM', native.watch_state(handle)['globals'])
        finally:
            native.watch_close(handle)
            globals().pop('WATCH_MUTATOR', None)
            globals().pop('WATCH_VICTIM', None)


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeAnalysis))
report = {'tests':result.testsRun, 'failures':len(result.failures), 'errors':len(result.errors),
          'skips':len(result.skipped), 'address_sanitizer':True, 'undefined_behavior_sanitizer':True,
          'leak_sanitizer':False, 'full_spell_executor_qualified':False}
Path('/out/analysis-runtime.json').write_text(json.dumps(report, indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
