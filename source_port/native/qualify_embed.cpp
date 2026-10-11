// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_WS/SPELLwsWarmStartImpl.H"
#include <iostream>
#include <thread>

int main() {
    auto& helper = SPELLpythonHelper::instance();
    for (int cycle = 0; cycle < 3; ++cycle) {
        helper.initialize();
        if (!helper.isInitialized() || !Py_IsInitialized()) return 10;
        bool rejected = false;
        std::thread wrongOwner([&] {
            try { helper.finalize(); }
            catch (const SPELLcoreException&) { rejected = true; }
        });
        wrongOwner.join();
        if (!rejected || !Py_IsInitialized()) return 11;
        {
            SPELLpython313::GIL gil;
            SPELLpython313::Owned filterKey(PyUnicode_FromString("previous_interpreter"));
            if (SPELLwsWarmStartImpl::shouldFilter(filterKey.get(), Py_None)) return 16;
            SPELLpython313::Owned filterKeys(PyTuple_Pack(1, filterKey.get()));
            SPELLwsWarmStartImpl::setGlobalsFilter(filterKeys.get());
            if (!SPELLwsWarmStartImpl::shouldFilter(filterKey.get(), Py_None)) return 17;
            SPELLpython313::Owned globals(PyDict_New());
            PyDict_SetItemString(globals.get(), "__builtins__", PyEval_GetBuiltins());
            SPELLpython313::Owned code(reinterpret_cast<PyObject*>(helper.compileScript("answer=6*7\n")));
            SPELLpython313::Owned result(PyEval_EvalCode(code.get(), globals.get(), globals.get()));
            if (!result.get() || PyLong_AsLong(PyDict_GetItemString(globals.get(), "answer")) != 42) return 12;
            if (PyDict_GetItemString(PyEval_GetBuiltins(), "Display")) return 13;
            bool syntax = false;
            try { Py_XDECREF(helper.compileScript("broken=\n")); }
            catch (const SPELLcoreException& error) { syntax = error.getCode() == SPELL_PYERROR_SYNTAX; }
            if (!syntax || PyErr_Occurred()) return 14;
        }
        helper.finalize();
        if (Py_IsInitialized() || helper.isInitialized()) return 15;
    }
    std::cout << "{\"owned_interpreter_cycles\":3,\"foreign_thread_finalize_rejected\":true}\n";
    return 0;
}
