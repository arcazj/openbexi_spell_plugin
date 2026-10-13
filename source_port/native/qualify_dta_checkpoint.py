"""Native DTA checkpoint graph qualification. SPDX-License-Identifier: GPL-3.0-or-later."""
import gc
import importlib.util
import json
from pathlib import Path
import pickle
import subprocess
import sys
import unittest
import weakref
import cloudpickle

sys.path.insert(0,'/source/src/spell')
extension=next(Path('/out').glob('libSPELL_DTA_v3*.so'))
def load(name):
    spec=importlib.util.spec_from_file_location(name,extension)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    sys.modules[name]=module
    return module
dta=load('libSPELL_DTA_v3');native=load('_spell_dta_qualification')
from spell.lang.constants import LONG,HEX
from spell.lib.exception import SyntaxException

class DataCheckpoints(unittest.TestCase):
    def setUp(self): native.notifications(False)
    def tearDown(self): native.notifications(False)
    def test_native_type_identity_does_not_require_adapter_import(self):
        # Explicit native imports must serialize by reference even when the
        # Python adapter alias has never been imported by a procedure.
        previous=sys.modules.pop('spell.lib.adapter.data',None)
        try:
            self.assertEqual(dta.DataContainer.__module__,'libSPELL_DTA_v3')
            self.assertEqual(dta.Var.__module__,'libSPELL_DTA_v3')
            original=dta.DataContainer('native-only')
            original['count']=dta.Var(Default=7)
            restored=cloudpickle.loads(cloudpickle.dumps(original,protocol=5))
            self.assertIs(type(restored),dta.DataContainer)
            self.assertEqual(restored['count'],7)
        finally:
            if previous is not None: sys.modules['spell.lib.adapter.data']=previous
    def test_primitive_and_nested_values(self):
        for value in (None,True,1234567890123,3.5,'value\x00終',[1,2],{'a':[1,2]}):
            variable=dta.Var(Default=value)
            for codec in (pickle,cloudpickle):
                restored=codec.loads(codec.dumps(variable,protocol=5))
                self.assertEqual(native.value(restored),value)
                self.assertEqual(native.details(restored),native.details(variable))
    def test_constraints_confirm_and_format(self):
        # LRM p.85 forbids combining Range and Expected. Qualify both valid
        # declarations independently, retaining confirmation and display format.
        for constraints,invalid in (({'Range':[0,10]},(-1,11,'bad')),
                                    ({'Expected':[3,5,7]},(-1,4,11,'bad'))):
            variable=dta.Var(Default=5,Type=LONG,ValueFormat=HEX,Confirm=True,**constraints)
            for codec in (pickle,cloudpickle):
                restored=codec.loads(codec.dumps(variable,protocol=5))
                self.assertEqual(restored.__reduce_ex__(5)[2][2],variable.__reduce_ex__(5)[2][2])
                for value in invalid:
                    with self.assertRaises(Exception): native.assign(restored,value)
                    self.assertEqual(native.value(restored),5)
                native.assign(restored,7)
                self.assertEqual(native.value(restored),7)
                self.assertEqual(native.value(variable),5)
    def test_mutually_exclusive_constraints_reject_and_restore_recovers(self):
        with self.assertRaisesRegex(SyntaxException,'Range and Expected cannot be combined'):
            dta.Var(Default=5,Type=LONG,Range=[0,10],Expected=[3,5,7])
        variable=dta.Var(Default=5,Type=LONG,Range=[0,10],ValueFormat=HEX,Confirm=True)
        state=variable.__reduce_ex__(5)[2]
        invalid=state[:2]+(dict(state[2],Expected=[3,5,7]),)+state[3:]
        # The private checkpoint codec reports malformed state as ValueError.
        with self.assertRaisesRegex(ValueError,'Range and Expected cannot be combined'):
            variable.__setstate__(invalid)
        self.assertEqual(variable.__reduce_ex__(5)[2][2],state[2])
        native.assign(variable,7)
        self.assertEqual(native.value(variable),7)
    def test_uninitialized_value_does_not_prompt(self):
        restored=pickle.loads(pickle.dumps(dta.Var(),protocol=5))
        self.assertIsNone(native.value(restored))
    def test_shared_variable_identity_and_original_parent(self):
        left=dta.DataContainer('left');right=dta.DataContainer('right')
        shared=dta.Var(Default=7)
        right[3.5]=shared
        left['last']=shared
        left.disableNotifications()
        # Serialization visits the opposite order from the last assignment.
        restored_left,restored_right,restored=cloudpickle.loads(cloudpickle.dumps((left,right,shared),protocol=5))
        self.assertIs(restored_left.values()[0],restored_right.values()[0])
        self.assertIs(restored_left.values()[0],restored)
        self.assertIs(restored.__reduce_ex__(5)[2][3],restored_left)
        self.assertEqual(restored.__reduce_ex__(5)[2][1],'last')
        self.assertFalse(restored_left.__reduce_ex__(5)[2][2])
        self.assertTrue(restored_right.__reduce_ex__(5)[2][2])
        self.assertEqual(restored_right.keys(),[3.5])
    def test_container_key_order_and_detach(self):
        original=dta.DataContainer('catalogue')
        original[1]=7;original['λ']=8;original[2.5]=9
        restored=pickle.loads(pickle.dumps(original,protocol=5))
        self.assertEqual(restored.keys(),[1,'λ',2.5])
        variable=restored.values()[0]
        self.assertEqual(native.value(variable),7)
        del restored;gc.collect()
        self.assertIsNone(variable.__reduce_ex__(5)[2][3])
    def test_restore_suppresses_notifications_and_restores_flag(self):
        original=dta.Var(Default=7,Confirm=True)
        payload=pickle.dumps(original,protocol=5)
        native.notifications(True)
        restored=pickle.loads(payload)
        self.assertEqual(native.value(restored),7)
        with self.assertRaisesRegex(Exception,'executor unavailable'): dta.Var(Default=1)
    def test_failed_variable_restore_preserves_value_and_notification_flag(self):
        value=dta.Var(Default=7,Type=LONG,Range=[0,10])
        state=value.__reduce_ex__(5)[2]
        invalid=state[:2]+(dict(state[2],Default=99),)+state[3:]
        native.notifications(True)
        with self.assertRaises(Exception): value.__setstate__(invalid)
        self.assertEqual(native.value(value),7)
        with self.assertRaisesRegex(Exception,'executor unavailable'): dta.Var(Default=1)
    def test_invalid_container_state_preserves_existing_values(self):
        value=dta.DataContainer('original');value['a']=7
        state=value.__reduce_ex__(5)[2]
        for invalid in (None,(),(2,)+state[1:],state[:3]+({'bad':1},state[4]),state[:3]+({object():dta.Var()},state[4])):
            with self.assertRaises(Exception): value.__setstate__(invalid)
            self.assertEqual(value['a'],7)
            self.assertEqual(value.__reduce_ex__(5)[2][1],'original')
    def test_reduction_cannot_mutate_private_dictionary(self):
        value=dta.DataContainer();value['a']=7
        state=value.__reduce_ex__(5)[2]
        state[3]['bad']=1
        self.assertEqual(value.keys(),['a'])
        self.assertEqual(value['a'],7)
    def test_subclass_dictionary_slots_and_cycles(self):
        class Container(dta.DataContainer):
            __slots__=('extra','__dict__')
        class Variable(dta.Var):
            __slots__=('extra','__dict__')
        container=Container('subclass');variable=Variable(Default=7)
        container['a']=variable
        container.extra=variable;variable.extra=container
        container.link=container;variable.link=variable
        restored=cloudpickle.loads(cloudpickle.dumps(container,protocol=5))
        value=restored.values()[0]
        self.assertIs(restored.extra,value)
        self.assertIs(value.extra,restored)
        self.assertIs(restored.link,restored)
        self.assertIs(value.link,value)
        self.assertEqual(native.value(value),7)
    def test_repeated_graph_release(self):
        class Container(dta.DataContainer): pass
        class Variable(dta.Var): pass
        container=Container('cycles');variable=Variable(Default=7)
        container['a']=variable;variable.owner=container
        payload=cloudpickle.dumps(container,protocol=5)
        refs=[]
        for _ in range(200):
            recovered=cloudpickle.loads(payload)
            refs.append(weakref.ref(recovered));refs.append(weakref.ref(recovered.values()[0]))
            del recovered
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))
    def test_invalid_factories_and_uninitialized_objects_fail(self):
        for factory in (dta._checkpoint_new_var,dta._checkpoint_new_container):
            for value in (None,int,object()):
                with self.assertRaises(TypeError): factory(value)
        for value in (dta.Var.__new__(dta.Var),dta.DataContainer.__new__(dta.DataContainer)):
            with self.assertRaises(Exception): pickle.dumps(value,protocol=5)

names=unittest.defaultTestLoader.getTestCaseNames(DataCheckpoints)
if len(sys.argv)==2:
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([DataCheckpoints(sys.argv[1])]))
    raise SystemExit(0 if result.wasSuccessful() else 1)
rows=[]
for name in names:
    result=subprocess.run([sys.executable,'-I',__file__,name],capture_output=True,text=True,timeout=20)
    Path('/out/dta-checkpoint-'+name+'.log').write_text(result.stdout+result.stderr)
    rows.append({'case':name,'exit_code':result.returncode})
report={'tests':len(rows),'failures':sum(row['exit_code']!=0 for row in rows),'cases':rows,
    'address_sanitizer':True,'undefined_behavior_sanitizer':True,'leak_sanitizer':False,
    'real_cif_notifications_qualified':False}
Path('/out/dta-checkpoint-runtime.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
raise SystemExit(1 if report['failures'] else 0)
