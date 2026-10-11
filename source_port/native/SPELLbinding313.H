// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef SPELL_BINDING313_H
#define SPELL_BINDING313_H
#include "SPELL_EXC/SPELLexecutor.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include <exception>
namespace SPELLbinding313 {
template<class Function> PyObject* guard(Function action) noexcept {
    try {
        if (!SPELLexecutor::isAvailable()) {
            PyErr_SetString(PyExc_RuntimeError,"SPELL binding requires an active executor");
            return nullptr;
        }
        PyObject* result=action();
        if (PyErr_Occurred()) { Py_XDECREF(result); return nullptr; }
        return result;
    } catch (SPELLcoreException& ex) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,ex.what().c_str());
    } catch (const std::exception& ex) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,ex.what());
    } catch (...) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,"Native SPELL binding failed");
    }
    return nullptr;
}
inline bool arity(PyObject* args, int minimum, int maximum) {
    Py_ssize_t count=args ? PyTuple_Size(args) : 0;
    if (count<0) return false;
    if (count<minimum || count>maximum) {
        PyErr_Format(PyExc_TypeError,"Expected %d to %d positional arguments, received %zd",minimum,maximum,count);
        return false;
    }
    return true;
}
template<PyObject* (*Function)(PyObject*,PyObject*), int Minimum, int Maximum>
PyObject* call(PyObject* self, PyObject* args) noexcept {
    return guard([&]() { return arity(args,Minimum,Maximum) ? Function(self,args) : nullptr; });
}
template<PyObject* (*Function)(PyObject*,PyObject*,PyObject*), int Minimum, int Maximum>
PyObject* keywords(PyObject* self, PyObject* args, PyObject* kwargs) noexcept {
    return guard([&]() { return arity(args,Minimum,Maximum) ? Function(self,args,kwargs) : nullptr; });
}
inline PyObject* instance(PyType_Spec* spec) {
    SPELLpython313::Owned type(PyType_FromSpec(spec));
    if (!type.get()) SPELLpythonHelper::instance().checkError();
    PyObject* object=PyObject_CallNoArgs(type.get());
    if (!object) SPELLpythonHelper::instance().checkError();
    return object;
}
}
#endif
