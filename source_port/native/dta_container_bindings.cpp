// SPDX-License-Identifier: GPL-3.0-or-later
// Python slots for the original data container; all native access is checked.
#include "SPELL_DTA/SPELLdtaContainerObject.H"
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include <memory>
namespace {
SPELLdtaContainer* container(PyObject* self) {
    auto* result = reinterpret_cast<SPELLdtaContainerObject*>(self)->container;
    if (!result) PyErr_SetString(PyExc_RuntimeError, "uninitialized DataContainer");
    return result;
}
bool keyOk(PyObject* key) {
    if (key && (PyUnicode_Check(key) || PyLong_Check(key) || PyFloat_Check(key))) return true;
    PyErr_SetString(PyExc_TypeError, "data key must be a string or number"); return false;
}
PyObject* error(const SPELLcoreException& e) {
    SPELLerror::instance().throwDriverException(e.getError(), e.getReason()); return nullptr;
}
}
int SPELLdtaContainerObject_Init(SPELLdtaContainerObject* self, PyObject* args, PyObject* keywords) {
    const char* name = "";
    if ((keywords && PyDict_Size(keywords)) || !PyArg_ParseTuple(args, "|s:DataContainer", &name)) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_TypeError, "DataContainer accepts one optional positional name");
        return -1;
    }
    try {
        auto fresh = std::make_unique<SPELLdtaContainer>(name);
        auto* previous = self->container;
        self->container = fresh.release();
        delete previous;
    } catch (const SPELLcoreException& e) { error(e); return -1; }
    return 0;
}
void SPELLdtaContainerObject_Dealloc(SPELLdtaContainerObject* self) {
    PyObject_GC_UnTrack(self);
    auto* type = Py_TYPE(self);
    auto* previous = self->container;
    self->container = nullptr;
    delete previous;
    type->tp_free(reinterpret_cast<PyObject*>(self));
    Py_DECREF(type); // heap-type reference owned by the allocation
}
PyObject* SPELLdtaContainerObject_New(PyTypeObject* type, PyObject*, PyObject*) { return type->tp_alloc(type, 0); }
PyObject* SPELLdtaContainerObject_Set(PyObject* self, PyObject* args) {
    PyObject *key, *value;
    if (!PyArg_ParseTuple(args, "OO:set", &key, &value)) return nullptr;
    if (SPELLdtaContainerObject_DictAssSub(self, key, value)<0) return nullptr;
    Py_RETURN_NONE;
}
PyObject* SPELLdtaContainerObject_Get(PyObject* self, PyObject* args) {
    PyObject* key;
    if (!PyArg_ParseTuple(args, "O:get", &key)) return nullptr;
    return SPELLdtaContainerObject_DictSubscript(self, key);
}
PyObject* SPELLdtaContainerObject_Keys(PyObject* self, PyObject*) {
    auto* value = container(self); return value ? value->getKeys() : nullptr;
}
PyObject* SPELLdtaContainerObject_Values(PyObject* self, PyObject*) {
    auto* value = container(self); return value ? PyDict_Values(value->getDict()) : nullptr;
}
PyObject* SPELLdtaContainerObject_Repr(PyObject* self) {
    auto* value = container(self); return value ? PyObject_Repr(value->getDict()) : nullptr;
}
PyObject* SPELLdtaContainerObject_Str(PyObject* self) { return SPELLdtaContainerObject_Repr(self); }
Py_ssize_t SPELLdtaContainerObject_DictLength(PyObject* self) {
    auto* value = container(self); return value ? value->getSize() : -1;
}
PyObject* SPELLdtaContainerObject_DictSubscript(PyObject* self, PyObject* key) {
    auto* value = container(self); if (!value || !keyOk(key)) return nullptr;
    try { return value->getValue(key); } catch (const SPELLcoreException& e) { return error(e); }
}
int SPELLdtaContainerObject_DictAssSub(PyObject* self, PyObject* key, PyObject* object) {
    auto* value = container(self); if (!value || !keyOk(key)) return -1;
    if (!object) { PyErr_SetString(PyExc_TypeError, "SPELL data containers do not support item deletion"); return -1; }
    try { value->setValue(key, object); } catch (const SPELLcoreException& e) { error(e); return -1; }
    return 0;
}
PyObject* SPELLdtaContainerObject_HasKey(PyObject* self, PyObject* args) {
    PyObject* key;
    if (!PyArg_ParseTuple(args, "O:has_key", &key)) return nullptr;
    auto* value = container(self); if (!value || !keyOk(key)) return nullptr;
    try { return PyBool_FromLong(value->hasKey(key)); } catch (const SPELLcoreException& e) { return error(e); }
}
int SPELLdtaContainerObject_Traverse(PyObject* self, visitproc visit, void* arg) {
    Py_VISIT(Py_TYPE(self));
    auto* value = reinterpret_cast<SPELLdtaContainerObject*>(self)->container;
    if (value) Py_VISIT(value->getDict());
    return 0;
}
int SPELLdtaContainerObject_Clear(PyObject* self) {
    auto* value = reinterpret_cast<SPELLdtaContainerObject*>(self)->container;
    if (value) value->clear();
    return 0;
}
PyObject* SPELLdtaContainerObject_Iter(SPELLdtaContainerObject* self) {
    auto* value = container(reinterpret_cast<PyObject*>(self));
    // The public dict iterator owns its dictionary and detects size changes.
    return value ? PyObject_GetIter(value->getDict()) : nullptr;
}
PyObject* SPELLdtaContainerObject_EnableNotifications(PyObject* self, PyObject*) {
    auto* value = container(self); if (!value) return nullptr;
    value->setNotificationsEnabled(true); Py_RETURN_NONE;
}
PyObject* SPELLdtaContainerObject_DisableNotifications(PyObject* self, PyObject*) {
    auto* value = container(self); if (!value) return nullptr;
    value->setNotificationsEnabled(false); Py_RETURN_NONE;
}
