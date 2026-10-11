"""Original DTA native type qualification. SPDX-License-Identifier: GPL-3.0-or-later."""
import gc
import importlib.util
import json
import operator
from pathlib import Path
import subprocess
import sys
import unittest
import weakref

sys.path.insert(0, '/source/src/spell') # original modules, not dummy SPELL objects
extension = next(Path('/out').glob('libSPELL_DTA_v3*.so'))
def load(name):
    spec = importlib.util.spec_from_file_location(name, extension)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module
    return module


class DataTypes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global native, dta, LONG, FLOAT, HEX
        dta = load('libSPELL_DTA_v3')
        native = load('_spell_dta_qualification')
        from spell.lang.constants import LONG, FLOAT, HEX
        native.notifications(False)

    def test_primitives_and_collection_roundtrip(self):
        for value in (True, False, -1234567890123, 3.5, 'text λ', [1, 'two', 3.5], {'a':[1, 2]}):
            self.assertEqual(native.roundtrip(value), value)

    def test_container_assign_get_and_order(self):
        container = dta.DataContainer('test')
        container.set('first', 10)
        container['second'] = 20
        container['first'] = 42
        self.assertEqual(container.get('first'), 42)
        self.assertEqual(container['second'], 20)
        self.assertEqual(container.keys(), ['first', 'second'])
        self.assertEqual(len(container), 2)
        self.assertTrue(container.has_key('first'))
        self.assertFalse(container.has_key('missing'))

    def test_numeric_keys_preserve_identity(self):
        container = dta.DataContainer()
        container[1] = 10
        container[2.5] = 20
        self.assertEqual(container.keys(), [1, 2.5])
        self.assertEqual(list(container), [1, 2.5])

    def test_var_subclass_and_replacement(self):
        class Var(dta.Var): pass
        container = dta.DataContainer()
        value = Var(Default=42)
        container['value'] = value
        self.assertIs(container.values()[0], value)
        container['value'] = dta.Var(Default=12)
        self.assertEqual(container['value'], 12)

    def test_container_destruction_releases_variables(self):
        class Var(dta.Var): pass
        refs = []
        for _ in range(500):
            container = dta.DataContainer()
            value = Var(Default=42)
            refs.append(weakref.ref(value))
            container['value'] = value
            del value, container
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))

    def test_reference_counts_after_reads_updates_and_iteration(self):
        container = dta.DataContainer()
        value = dta.Var(Default=42)
        container['value'] = value
        before = sys.getrefcount(value)
        for _ in range(1000):
            self.assertEqual(container['value'], 42)
            container['value'] = 42
            container.keys()
            container.values()
            list(container)
        self.assertEqual(sys.getrefcount(value), before)

    def test_iterator_lifetime_and_size_mutation(self):
        container = dta.DataContainer()
        container['a'] = 1
        container['b'] = 2
        iterator = iter(container)
        self.assertEqual(operator.length_hint(iterator), 2)
        del container
        self.assertEqual(list(iterator), ['a', 'b'])
        container = dta.DataContainer()
        container['a'] = 1
        iterator = iter(container)
        container['b'] = 2
        with self.assertRaises(RuntimeError): next(iterator)

    def test_invalid_arguments_return_python_errors(self):
        container = dta.DataContainer()
        for operation in (lambda: container.get(), lambda: container.get(1,2),
                          lambda: container.set('x'), lambda: container.has_key(),
                          lambda: container.__setitem__([], 1), lambda: container.__delitem__('x')):
            with self.assertRaises(Exception): operation()

    def test_uninitialized_instances_are_safe(self):
        container = dta.DataContainer.__new__(dta.DataContainer)
        variable = dta.Var.__new__(dta.Var)
        for operation in (lambda: len(container), lambda: container.keys(), lambda: repr(container),
                          lambda: repr(variable), lambda: str(variable)):
            with self.assertRaises(Exception): operation()

    def test_original_var_range_expected_type_and_format(self):
        ranged = dta.Var(Default=5, Range=[0,10], Type=LONG)
        native.assign(ranged, 7)
        self.assertEqual(native.value(ranged), 7)
        for value in (-1, 11, 'bad'):
            with self.assertRaises(RuntimeError): native.assign(ranged, value)
        expected = dta.Var(Default='a', Expected=['a','b'])
        native.assign(expected, 'b')
        self.assertEqual(native.value(expected), 'b')
        with self.assertRaises(RuntimeError): native.assign(expected, 'c')
        formatted = dta.Var(Default=255, Type=LONG, ValueFormat=HEX)
        self.assertEqual(native.details(formatted), {'type':LONG, 'format':HEX})
        self.assertEqual(str(formatted), '255') # original str() is unformatted; CIF applies the format

    def test_float_conversion_keeps_large_integer(self):
        value = dta.Var(Default=1.0, Type=FLOAT)
        native.assign(value, 2**40)
        self.assertEqual(native.value(value), float(2**40))

    def test_recursive_input_is_rejected(self):
        value = []
        value.append(value)
        with self.assertRaises(Exception): native.roundtrip(value)

    def test_container_and_variable_subclass_cycles_are_collected(self):
        class Var(dta.Var): pass
        class Container(dta.DataContainer): pass
        container = Container()
        variable = Var(Default=42)
        container['value'] = variable
        variable.parent = container
        refs = [weakref.ref(container), weakref.ref(variable)]
        del container, variable
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))

    def test_reinitialization_releases_old_values_and_failed_init_preserves(self):
        class Var(dta.Var): pass
        container = dta.DataContainer()
        variable = Var(Default=42)
        ref = weakref.ref(variable)
        container['value'] = variable
        del variable
        container.__init__('reloaded')
        self.assertIsNone(ref())
        self.assertEqual(container.keys(), [])
        value = dta.Var(Default=42)
        with self.assertRaises(Exception): value.__init__(1)
        self.assertEqual(native.value(value), 42)

    def test_native_value_assignment_replaces_collections(self):
        for first, second in [([1,2], [3]), ({'old':1}, {'new':2}), ([1], 42), (42, [1,2])]:
            self.assertEqual(native.replace(first, second), second)

    def test_repeated_shared_values_and_depth_limit(self):
        shared = [1, 2]
        self.assertEqual(native.roundtrip([shared, shared]), [[1,2], [1,2]])
        too_deep = 1
        for _ in range(140): too_deep = [too_deep]
        with self.assertRaisesRegex(RuntimeError, '128 levels'): native.roundtrip(too_deep)
        self.assertEqual(native.roundtrip([1,2]), [1,2])

    def test_strings_keep_unicode_and_embedded_nulls(self):
        value = {'key\x00λ':'value\x00終', 'nested':['text\x00end']}
        self.assertEqual(native.roundtrip(value), value)

    def test_missing_executor_reports_error_instead_of_aborting(self):
        native.notifications(True)
        try:
            with self.assertRaisesRegex(Exception, 'executor unavailable'):
                dta.Var(Default=1)
        finally:
            native.notifications(False)
        container = dta.DataContainer()
        with self.assertRaisesRegex(Exception, 'executor unavailable'):
            container['unknown']
        container['known'] = dta.Var(Default=5, Range=[0,10])
        with self.assertRaisesRegex(Exception, 'executor unavailable'):
            container['known'] = 20
        self.assertEqual(container['known'], 5)


names = unittest.defaultTestLoader.getTestCaseNames(DataTypes)
if len(sys.argv) == 2:
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([DataTypes(sys.argv[1])]))
    raise SystemExit(0 if result.wasSuccessful() else 1)
rows = []
for name in names:
    result = subprocess.run([sys.executable, '-I', __file__, name], capture_output=True, text=True, timeout=15)
    Path('/out/dta-'+name+'.log').write_text(result.stdout+result.stderr)
    rows.append({'case':name,'exit_code':result.returncode})
report = {'tests':len(rows),'failures':sum(row['exit_code']!=0 for row in rows), 'cases':rows,
          'address_sanitizer':True,'undefined_behavior_sanitizer':True,'leak_sanitizer':False,
          'notifications_and_prompts_qualified':False}
Path('/out/dta-runtime.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
raise SystemExit(1 if report['failures'] else 0)
