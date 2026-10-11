// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_DTA/SPELLdtaContainer.H"
#include <iostream>
extern "C" PyObject* PyInit_libSPELL_DTA_v3();
int main() {
    if (PyImport_AppendInittab("libSPELL_DTA_v3", PyInit_libSPELL_DTA_v3)<0) return 1;
    auto& helper = SPELLpythonHelper::instance();
    for (int cycle=0; cycle<3; ++cycle) {
        helper.initialize();
        {
            SPELLpython313::GIL gil;
            helper.addToPath("/source/src/spell");
            SPELLdtaContainer::setGlobalNotificationsEnabled(false);
            const char* source = R"DTA(
import gc, sys, weakref
import libSPELL_DTA_v3 as dta
from spell.lang.constants import LONG
class Var(dta.Var): pass
baseline = sys.getrefcount(Var)
refs = []
for _ in range(1000):
    container = dta.DataContainer()
    value = Var(Default=42, Type=LONG)
    refs.append(weakref.ref(value))
    container['value'] = value
    assert container['value'] == 42
    del value, container
gc.collect()
assert all(ref() is None for ref in refs)
assert sys.getrefcount(Var) == baseline
)DTA";
            if (PyRun_SimpleString(source) < 0) { PyErr_Print(); return 2; }
        }
        helper.finalize();
        if (Py_IsInitialized()) return 3;
    }
    std::cout << "{\"owned_interpreter_cycles\":3,\"container_lifetimes\":3000}\n";
    return 0;
}
