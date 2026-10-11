// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef SPELL_CONTINUATION_313_H
#define SPELL_CONTINUATION_313_H
#include <Python.h>
#include <frameobject.h>
namespace SPELLcontinuation313 {
// GIL required. Returned Python references are owned; nullptr/-1 leave PyErr.
PyObject* snapshot(PyFrameObject* frame, PyObject* handled);
PyFrameObject* inspection(PyObject* state);
int callerOffset(PyFrameObject* parent, PyFrameObject* child);
PyObject* resume(PyObject* state);
PyObject* module();
}
#endif
