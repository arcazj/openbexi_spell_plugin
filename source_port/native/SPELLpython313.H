// SPDX-License-Identifier: GPL-3.0-or-later
// CPython 3.13 ownership helpers for the original SPELL native implementation.
#ifndef SPELL_PYTHON313_H
#define SPELL_PYTHON313_H
#include <Python.h>
#include <frameobject.h>
#include <string>
#if PY_MAJOR_VERSION != 3 || PY_MINOR_VERSION != 13 || defined(Py_GIL_DISABLED)
#error "This native port requires a GIL-enabled CPython 3.13 build"
#endif

namespace SPELLpython313 {
class Owned {
    PyObject* object;
public:
    explicit Owned(PyObject* value = nullptr): object(value) {}
    ~Owned() { Py_XDECREF(object); }
    Owned(const Owned&) = delete;
    Owned& operator=(const Owned&) = delete;
    PyObject* get() const { return object; }
};

class GIL {
    PyGILState_STATE state;
public:
    GIL(): state(PyGILState_Ensure()) {}
    ~GIL() { PyGILState_Release(state); }
    GIL(const GIL&) = delete;
    GIL& operator=(const GIL&) = delete;
};

inline std::string text(PyObject* object) {
    if (!object) return "<unavailable>";
    Owned rendered(PyObject_Str(object));
    if (!rendered.get()) { PyErr_Clear(); return "<unprintable>"; }
    Py_ssize_t size = 0;
    const char* value = PyUnicode_AsUTF8AndSize(rendered.get(), &size);
    if (!value) { PyErr_Clear(); return "<unprintable>"; }
    return std::string(value, size);
}

inline std::string filename(PyFrameObject* frame) {
    Owned code(reinterpret_cast<PyObject*>(PyFrame_GetCode(frame)));
    if (!code.get()) return "<unavailable>";
    Owned name(PyObject_GetAttrString(code.get(), "co_filename"));
    return text(name.get());
}
}
#endif
