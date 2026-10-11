// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_PRD/SPELLserviceWatchdogPython.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include <exception>
namespace {
using Callback=void (*)(std::string&);
struct OwnedCallback { Callback function; };
void destroyCallback(PyObject* capsule) {
    delete static_cast<OwnedCallback*>(PyCapsule_GetPointer(capsule,"SPELL.serviceWatchdog"));
}
PyObject* invokeCallback(PyObject* capsule,PyObject* target) noexcept {
    if (!PyUnicode_Check(target)) {
        PyErr_SetString(PyExc_TypeError,"Service name must be a string"); return nullptr;
    }
    const char* value=PyUnicode_AsUTF8(target);
    if (!value) return nullptr;
    auto* callback=static_cast<OwnedCallback*>(PyCapsule_GetPointer(capsule,"SPELL.serviceWatchdog"));
    if (!callback) return nullptr;
    try {
        std::string name(value);
        callback->function(name);
        Py_RETURN_NONE;
    } catch (SPELLcoreException& error) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,error.what().c_str());
    } catch (const std::exception& error) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,error.what());
    } catch (...) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,"Service watchdog failed");
    }
    return nullptr;
}
}
PyObject* SpellServiceWatchdog_Create(Callback callback)
{
    if (!callback) { PyErr_SetString(PyExc_ValueError,"Watchdog callback is null"); return nullptr; }
    auto* value=new OwnedCallback{callback};
    SPELLpython313::Owned capsule(PyCapsule_New(value,"SPELL.serviceWatchdog",destroyCallback));
    if (!capsule.get()) { delete value; return nullptr; }
    static PyMethodDef method={"WatchdogCallback",invokeCallback,METH_O,"Original SPELL service watchdog"};
    return PyCFunction_NewEx(&method,capsule.get(),nullptr);
}
