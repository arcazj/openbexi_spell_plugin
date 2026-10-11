// SPDX-License-Identifier: GPL-3.0-or-later
// Port of SPELLwsWarmStartImpl filtering, Copyright (C) 2008, 2018
// SES ENGINEERING, Luxembourg S.A.R.L. Interpreter-local ownership replaces
// the upstream static PyObject*, which survived interpreter finalization.
#include "SPELL_WS/SPELLwsWarmStartImpl.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include "SPELL_WRP/SPELLconstants.H"

namespace {
constexpr const char* filterName = "openbexi.spell.ws.globals_filter";
PyObject* state() {
    PyObject* dict = PyInterpreterState_GetDict(PyInterpreterState_Get());
    if (!dict) {
        PyErr_NoMemory();
        SPELLpythonHelper::instance().checkError();
    }
    return dict; // interpreter owns this dictionary
}
}

void SPELLwsWarmStartImpl::setGlobalsFilter(PyObject* keys) {
    SPELLpython313::GIL gil;
    SPELLpython313::Owned filter(PySet_New(keys)); // NULL clears the set
    if (!filter.get() || PyDict_SetItemString(state(), filterName, filter.get()) < 0)
        SPELLpythonHelper::instance().checkError();
}

bool SPELLwsWarmStartImpl::shouldFilter(PyObject* key, PyObject* value) {
    SPELLpython313::GIL gil;
    if (!key || !value || !PyUnicode_Check(key)) {
        PyErr_SetString(PyExc_TypeError, "warm-start globals require a string key and a value");
        SPELLpythonHelper::instance().checkError();
    }
    if (PyModule_Check(value) || PyCallable_Check(value)) return true;
    const auto name = SPELLpython313::text(key);
    if (name == DatabaseConstants::SCDB || name == DatabaseConstants::GDB || name == DatabaseConstants::PROC)
        return true;
    PyObject* filter = PyDict_GetItemString(state(), filterName); // borrowed
    if (!filter) return false;
    int contains = PySet_Contains(filter, key);
    if (contains < 0) SPELLpythonHelper::instance().checkError();
    return contains != 0;
}
