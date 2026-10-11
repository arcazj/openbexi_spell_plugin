// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef SPELL_ANALYSIS313_H
#define SPELL_ANALYSIS313_H
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include "SPELL_UTIL/SPELLanalysisSource.H"
namespace SPELLanalysis313 {
inline PyObject* module() {
    PyObject* modules = PyImport_GetModuleDict();
    PyObject* existing = PyDict_GetItemString(modules, "_spell_cpython313_analysis");
    if (existing) {
        if (!PyModule_Check(existing)) {
            PyErr_SetString(PyExc_ImportError, "invalid native analysis module");
            SPELLpythonHelper::instance().checkError();
        }
        return Py_NewRef(existing);
    }
    SPELLpython313::Owned created(PyModule_New("_spell_cpython313_analysis"));
    if (!created.get()) SPELLpythonHelper::instance().checkError();
    PyObject* globals = PyModule_GetDict(created.get());
    if (PyDict_SetItemString(globals, "__builtins__", PyEval_GetBuiltins()) < 0)
        SPELLpythonHelper::instance().checkError();
    SPELLpython313::Owned loaded(PyRun_StringFlags(analysisSource, Py_file_input, globals, globals, nullptr));
    if (!loaded.get() || PyDict_SetItemString(modules, "_spell_cpython313_analysis", created.get()) < 0)
        SPELLpythonHelper::instance().checkError();
    return Py_NewRef(created.get());
}
inline void remember(PyObject* code, const std::string& source) {
    SPELLpython313::Owned owner(module());
    SPELLpython313::Owned bytes(PyBytes_FromStringAndSize(source.data(), source.size()));
    if (!bytes.get()) SPELLpythonHelper::instance().checkError();
    SPELLpython313::Owned result(PyObject_CallMethod(owner.get(), "remember", "OO", code, bytes.get()));
    if (!result.get()) SPELLpythonHelper::instance().checkError();
}
inline PyObject* describe(PyCodeObject* code) {
    SPELLpython313::Owned owner(module());
    PyObject* result = PyObject_CallMethod(owner.get(), "describe", "O", reinterpret_cast<PyObject*>(code));
    if (!result) SPELLpythonHelper::instance().checkError();
    return result;
}
}
#endif
