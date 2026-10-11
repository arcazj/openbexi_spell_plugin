"""Independent runtime checks using the original native service manager.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import threading
import time
import unittest
from spell import runtime
from spell.utils.spell_service import SpellService, SupportServices

wrapper=SpellService(name='binding-service')
@wrapper
class Service:
    def __init__(self,name): self.name=name
    def startService(self): pass
    def isAlive(self): return False
service=Service

class ServiceBindings(unittest.TestCase):
    def test_registration_namespace(self):
        self.assertTrue(SupportServices())
        self.assertEqual(wrapper.getName(),'binding-service')
        self.assertEqual(wrapper.getMainFile(),__file__)
        self.assertEqual(service.name,'binding-service')

    def test_registration_arguments(self):
        for args in ((),(None,),(wrapper,wrapper)):
            with self.subTest(args=len(args)):
                with self.assertRaises((TypeError,AttributeError)):
                    runtime._register_service(*args)
        with self.assertRaises(TypeError): runtime._register_service(service=wrapper)

    def test_duplicate_service(self):
        with self.assertRaisesRegex(RuntimeError,'Duplicate name'):
            runtime.RegisterSpellService(wrapper)
        self.assertEqual(service.execute(lambda:42).result(timeout=3),42)

    def test_invalid_metadata(self):
        class Bad:
            def getName(self): return None
        with self.assertRaises(TypeError): runtime.RegisterSpellService(Bad())

    def test_worker_result_and_exception(self):
        self.assertEqual(service.execute(lambda x,y:x+y,20,y=22).result(timeout=3),42)
        def fail(): raise ValueError('worker error')
        with self.assertRaisesRegex(ValueError,'worker error'):
            service.execute(fail).result(timeout=3)

    def test_repeating_worker(self):
        self.event=threading.Event()
        worker=service.repeatFunction(self.event.set,0.01)
        self.assertTrue(self.event.wait(3))
        self.assertTrue(worker.is_alive())
        with self.assertRaises(ValueError): service.repeatFunction(lambda:None,0)

    def test_watchdog_boundaries(self):
        callback=runtime._qualificationWatchdog
        callback('direct')
        for args in ((),(1,),('a','b')):
            with self.assertRaises(TypeError): callback(*args)
        with self.assertRaisesRegex(RuntimeError,'Watchdog failure'): callback('raise')

    def test_watchdog_lifecycle(self):
        wrapper._startWatchDog(runtime._qualificationWatchdog)
        time.sleep(1.1)
        wrapper._startWatchDog(runtime._qualificationWatchdog)
        self.assertEqual(sum(t.name=='repeating Thread' for t in threading.enumerate()),2)

suite=unittest.defaultTestLoader.loadTestsFromTestCase(ServiceBindings)
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful(): raise RuntimeError('Native service binding checks failed')
print('SERVICE_BINDING_TESTS',result.testsRun,flush=True)
