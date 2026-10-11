// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_PRD/SPELLservicePython.H"
#include "SPELL_PRD/SPELLserviceWatchdogPython.H"
#include "SPELL_PRD/SPELLprocedureManager.H"
#include <atomic>
#include <iostream>
#include <stdexcept>
static std::atomic_int calls{0};
static void watchdog(std::string& name) {
    if (name=="raise") throw std::runtime_error("Watchdog failure propagated");
    if (name!="binding-service" && name!="direct") throw std::runtime_error("Unexpected service name");
    ++calls;
}
int main() {
    auto& helper=SPELLpythonHelper::instance();
    try {
        helper.initialize();
        {
            SPELLpython313::GIL gil;
            if (PyRun_SimpleString("import builtins,threading\n_original_builtins=dict(vars(builtins))\n_original_threads=set(threading.enumerate())\n")) return 1;
            SpellService_Install();
            helper.loadFramework();
            SPELLpython313::Owned callback(SpellServiceWatchdog_Create(watchdog));
            helper.install(callback.get(),"_qualificationWatchdog");
            helper.addToPath("/context");
            SPELLpython313::Owned tests(PyImport_ImportModule("qualify_service_bindings"));
            if (!tests.get()) { PyErr_Print(); return 2; }
            SPELLprocedureManager::instance().cleanupServices();
            if (!SPELLprocedureManager::instance().getServiceList().empty()) return 3;
            if (PyRun_SimpleString(R"PY(
import qualify_service_bindings as tests
assert vars(builtins)==_original_builtins
assert set(threading.enumerate())==_original_threads
assert tests.wrapper._threads==[]
for action in (lambda: tests.service.execute(lambda: None),
               lambda: tests.service.repeatFunction(lambda: None,0.01)):
    try:
        action()
        raise AssertionError('Stopped service accepted work')
    except RuntimeError:
        pass
print('SERVICE_WORKERS_JOINED',flush=True)
)PY")) return 4;
        }
        helper.finalize();
        if (Py_IsInitialized() || calls<2) return 5;
    } catch (SPELLcoreException& error) { std::cerr<<error.what()<<std::endl; return 6; }
    std::cout<<"SERVICE_BINDINGS_COMPLETE callbacks="<<calls<<std::endl;
}
