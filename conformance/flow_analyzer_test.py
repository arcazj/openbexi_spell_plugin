"""Adversarial label expectations independent of the native scanner algorithm."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'source_port/flow_analyze.py'
specification = importlib.util.spec_from_file_location('flow_analyze', path)
module = importlib.util.module_from_spec(specification)
specification.loader.exec_module(module)


def labels(source, nested=False):
    code = compile(source, '<flow-label-oracle>', 'exec')
    if nested:
        code = next(value for value in code.co_consts if hasattr(value, 'co_code'))
    return {(kind, label) for kind, label, title, offset in module.analyze_flow(code)}


class StaticLabelTests(unittest.TestCase):
    def test_literal_label_accepts_each_dynamic_title_shape(self):
        for title in ("value", "compute()", "str(3) + str(4)",
                      "left if condition else right", "left or right", "left and right"):
            with self.subTest(title=title):
                self.assertEqual(labels("Step('A', " + title + ")\nGoto('A')"),
                                 {('Step', 'A'), ('Goto', 'A')})

    def test_dynamic_or_conditional_first_argument_is_not_guessed(self):
        for first in ('label', 'compute()', "items[0]", "'A' if flag else 'B'"):
            with self.subTest(first=first):
                self.assertEqual(labels("Step(" + first + ", 'title')"), set())
        self.assertEqual(labels("Goto(compute())"), set())

    def test_unrelated_literals_calls_and_attributes_do_not_create_labels(self):
        source = """
value = 'Step'
other('A', 'Title')
object.Step('B', 'Not the native symbol')
Step(label, 'C')
Goto(compute('D'))
"""
        self.assertEqual(labels(source), set())

    def test_function_scope_and_exception_handler_bytecode(self):
        source = """
def function(value):
    try:
        Step('TRY', value)
    except ValueError:
        Step('HANDLER', value)
    Goto('TRY')
"""
        self.assertEqual(labels(source, nested=True),
                         {('Step', 'TRY'), ('Step', 'HANDLER'), ('Goto', 'TRY')})
        self.assertEqual(labels(source), set())

    def test_rejected_keyword_and_spread_calls_do_not_become_labels(self):
        self.assertEqual(labels("Step('A', title='Title')"), set())
        self.assertEqual(labels("Step(*('A', 'Title'))"), set())

    def test_branch_and_loop_labels_remain_local(self):
        source = """
for index in range(3):
    Step('LOOP', str(index))
if condition:
    Step('LEFT', compute())
else:
    Step('RIGHT', compute())
"""
        self.assertEqual(labels(source), {('Step', 'LOOP'), ('Step', 'LEFT'), ('Step', 'RIGHT')})


if __name__ == '__main__':
    unittest.main()
