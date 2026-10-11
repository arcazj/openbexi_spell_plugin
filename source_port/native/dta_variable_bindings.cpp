// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_DTA/SPELLdtaVariableObject.H"
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include <memory>
int SPELLdtaVariableObject_Init(SPELLdtaVariableObject* self, PyObject* args, PyObject* keywords) {
    if (PyTuple_Size(args) != 0) {
        SPELLerror::instance().throwSyntaxException("Cannot create variable container", "Expected no positional arguments"); return -1;
    }
    try {
        auto fresh = std::make_unique<SPELLdtaVariable>(keywords);
        auto* previous = self->var;
        self->var = fresh.release();
        delete previous;
    } catch (const SPELLcoreException& e) {
        SPELLerror::instance().throwSyntaxException(e.getError(), e.getReason()); return -1;
    }
    return 0;
}
void SPELLdtaVariableObject_Dealloc(SPELLdtaVariableObject* self) {
    auto* type = Py_TYPE(self);
    delete self->var;
    type->tp_free(reinterpret_cast<PyObject*>(self));
    Py_DECREF(type);
}
PyObject* SPELLdtaVariableObject_New(PyTypeObject* type, PyObject*, PyObject*) { return type->tp_alloc(type, 0); }
PyObject* SPELLdtaVariableObject_Repr(PyObject* self) {
    auto* value = reinterpret_cast<SPELLdtaVariableObject*>(self)->var;
    if (!value) { PyErr_SetString(PyExc_RuntimeError, "uninitialized Var"); return nullptr; }
    try {
        auto text = value->repr();
        return PyUnicode_FromStringAndSize(text.data(), text.size());
    } catch (const SPELLcoreException& e) {
        SPELLerror::instance().throwDriverException(e.getError(), e.getReason()); return nullptr;
    }
}
PyObject* SPELLdtaVariableObject_Str(PyObject* self) {
    auto* value = reinterpret_cast<SPELLdtaVariableObject*>(self)->var;
    if (!value) { PyErr_SetString(PyExc_RuntimeError, "uninitialized Var"); return nullptr; }
    try {
        auto text = value->str();
        return PyUnicode_FromStringAndSize(text.data(), text.size());
    } catch (const SPELLcoreException& e) {
        SPELLerror::instance().throwDriverException(e.getError(), e.getReason()); return nullptr;
    }
}
