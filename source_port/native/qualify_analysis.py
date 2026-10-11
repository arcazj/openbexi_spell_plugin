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


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeAnalysis))
report = {'tests':result.testsRun, 'failures':len(result.failures), 'errors':len(result.errors),
          'skips':len(result.skipped), 'address_sanitizer':True, 'undefined_behavior_sanitizer':True,
          'leak_sanitizer':False, 'full_spell_executor_qualified':False}
Path('/out/analysis-runtime.json').write_text(json.dumps(report, indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
