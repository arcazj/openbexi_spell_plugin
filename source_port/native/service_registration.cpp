// SPDX-License-Identifier: GPL-3.0-or-later
// CPython callable for the original procedure manager's service registration.
#include "SPELL_PRD/SPELLservicePython.H"
#include "SPELL_PRD/SPELLprocedureManager.H"
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include <exception>
static PyObject* registerService(PyObject*, PyObject* target) noexcept
{
    try {
        for (const char* name : {"getName", "getBasePath", "getMainFile"}) {
            SPELLpython313::Owned result(PyObject_CallMethod(target,name,nullptr));
            if (!result.get()) return nullptr;
            if (!PyUnicode_Check(result.get()) || PyUnicode_GetLength(result.get())==0) {
                PyErr_SetString(PyExc_TypeError,"Service metadata must be nonempty strings");
                return nullptr;
            }
        }
        SPELLprocedureManager::instance().registerServiceHandler(target);
        return Py_NewRef(target);
    } catch (SPELLcoreException& error) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,error.what().c_str());
    } catch (const std::exception& error) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,error.what());
    } catch (...) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,"Service registration failed");
    }
    return nullptr;
}
void SpellService_Install()
{
    static PyMethodDef method={"RegisterSpellService",registerService,METH_O,"Register an original SPELL service"};
    SPELLpython313::Owned callable(PyCFunction_NewEx(&method,nullptr,nullptr));
    if (!callable.get()) SPELLpythonHelper::instance().checkError();
    SPELLpythonHelper::instance().install(callable.get(),"_register_service");
}
