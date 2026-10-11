// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_UTIL/SPELLlog.H"
#include "SPELL_EXC/SPELLexecutor.H"
#include "SPELL_EXC/SPELLgoto.H"
#include "SPELL_CIF/SPELLcif.H"
#include <iostream>

int main(int argc,char**)
{
    auto& helper=SPELLpythonHelper::instance();
    try {
        // Native binding lifetimes can span interpreter cycles. The full RPC
        // stack includes gRPC, which is qualified in a fresh process instead.
        const int cycles=argc>1 ? 1 : 3;
        for (int cycle=0; cycle<cycles; ++cycle) {
            helper.initialize();
            {
                SPELLpython313::GIL gil;
                if (PyRun_SimpleString("import builtins\n_original_builtins=dict(vars(builtins))\n")) return 1;
                Log_Install();
                if (argc>1) helper.loadFramework();
                else {
                    SPELLpython313::Owned registry(PyImport_ImportModule("spell.lib.registry"));
                    if (!registry.get()) helper.checkError();
                }
                if (PyRun_SimpleString("import weakref,gc\n_binding_types=[]\n")) return 2;
                for (int count=0; count<200; ++count) {
                    Executor_Install(); ClientIF_Install(); Step_Install(); Goto_Install();
                    if (PyRun_SimpleString(R"PY(
from spell.lib.registry import REGISTRY
from spell import runtime
for obj in (REGISTRY['EXEC'],REGISTRY['CIF'],runtime.Step,runtime.Goto):
    _binding_types.append(weakref.ref(type(obj)))
del obj
try:
    REGISTRY['EXEC'].getStatus()
    raise AssertionError('Missing executor accepted')
except RuntimeError as exc:
    assert 'active executor' in str(exc)
try:
    REGISTRY['CIF'].write('message')
    raise AssertionError('Missing CIF accepted')
except RuntimeError as exc:
    assert 'active executor' in str(exc)
for operation in (runtime.Step,runtime.Goto):
    try:
        operation()
        raise AssertionError('Missing executor accepted')
    except RuntimeError as exc:
        assert 'active executor' in str(exc)
del operation
)PY")) return 3;
                }
                if (PyRun_SimpleString(R"PY(
gc.collect()
assert sum(ref() is not None for ref in _binding_types)==4
assert vars(builtins)==_original_builtins
from spell.utils.log import LOG
import pickle
for binding in (REGISTRY['EXEC'],REGISTRY['CIF'],runtime.Step,runtime.Goto,LOG):
    assert pickle.loads(pickle.dumps(binding)) is binding
del binding
for severity in ('missing','',None,123):
    try:
        LOG('probe',severity=severity)
        raise AssertionError('Invalid severity accepted')
    except (TypeError,ValueError):
        pass
LOG('binding lifecycle probe')
)PY")) return 4;
            }
            helper.finalize();
            if (Py_IsInitialized()) return 5;
        }
        if (argc>1) {
            bool rejected=false;
            try { helper.initialize(); }
            catch (SPELLcoreException& error) {
                rejected=error.what().find("fresh executor process")!=std::string::npos;
            }
            if (!rejected || Py_IsInitialized()) return 7;
        }
    } catch (SPELLcoreException& error) {
        std::cerr<<error.what()<<std::endl; return 6;
    }
    std::cout<<"{\"cycles\":"<<(argc>1 ? 1 : 3)<<",\"binding_type_lifetimes\":"<<(argc>1 ? 800 : 2400)
             <<",\"builtins_unchanged\":true}"<<std::endl;
    return 0;
}
