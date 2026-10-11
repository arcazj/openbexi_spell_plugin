// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_DTA/SPELLdtaContainer.H"
#include "SPELL_DTA/SPELLdtaVariableObject.H"
#include "SPELL_UTIL/SPELLpython313.H"
static PyObject* fail(const SPELLcoreException& error) {
    PyErr_SetString(PyExc_RuntimeError, (error.getError()+": "+error.getReason()).c_str()); return nullptr;
}
static PyObject* notifications(PyObject*, PyObject* value) {
    int enabled = PyObject_IsTrue(value); if (enabled < 0) return nullptr;
    SPELLdtaContainer::setGlobalNotificationsEnabled(enabled); Py_RETURN_NONE;
}
static SPELLdtaVariable* variable(PyObject* object) {
    SPELLpython313::Owned module(PyImport_ImportModule("libSPELL_DTA_v3"));
    if (!module.get()) return nullptr;
    SPELLpython313::Owned type(PyObject_GetAttrString(module.get(), "Var"));
    if (!type.get()) return nullptr;
    if (!PyType_Check(type.get()) || !PyObject_TypeCheck(object, reinterpret_cast<PyTypeObject*>(type.get()))) {
        PyErr_SetString(PyExc_TypeError, "expected original Var"); return nullptr;
    }
    auto* value = reinterpret_cast<SPELLdtaVariableObject*>(object)->var;
    if (!value) PyErr_SetString(PyExc_RuntimeError, "uninitialized Var");
    return value;
}
static PyObject* assign(PyObject*, PyObject* args) {
    PyObject *object, *value;
    if (!PyArg_ParseTuple(args, "OO", &object, &value)) return nullptr;
    auto* var = variable(object); if (!var) return nullptr;
    try { var->setValue(value); } catch (const SPELLcoreException& e) { return fail(e); }
    Py_RETURN_NONE;
}
static PyObject* value(PyObject*, PyObject* object) {
    auto* var = variable(object); if (!var) return nullptr;
    try { return var->getValueEx(); } catch (const SPELLcoreException& e) { return fail(e); }
}
static PyObject* details(PyObject*, PyObject* object) {
    auto* var = variable(object); if (!var) return nullptr;
    return Py_BuildValue("{s:s,s:s}", "type", var->getType().c_str(), "format", var->getFormat().c_str());
}
static PyObject* roundtrip(PyObject*, PyObject* object) {
    try { return SPELLpyValue(object).get(); } catch (const SPELLcoreException& e) { return fail(e); }
}
static PyObject* replace(PyObject*, PyObject* args) {
    PyObject *first, *second;
    if (!PyArg_ParseTuple(args, "OO", &first, &second)) return nullptr;
    try {
        SPELLpyValue value(first), replacement(second);
        value = replacement;
        value = value; // self assignment must not append to its own collection
        return value.get();
    } catch (const SPELLcoreException& e) { return fail(e); }
}
static PyMethodDef methods[] = {
    {"notifications",notifications,METH_O,nullptr}, {"assign",assign,METH_VARARGS,nullptr},
    {"value",value,METH_O,nullptr}, {"details",details,METH_O,nullptr},
    {"roundtrip",roundtrip,METH_O,nullptr}, {"replace",replace,METH_VARARGS,nullptr}, {nullptr,nullptr,0,nullptr}
};
static PyModuleDef module = {PyModuleDef_HEAD_INIT,"_spell_dta_qualification",nullptr,-1,methods};
PyMODINIT_FUNC PyInit__spell_dta_qualification() { return PyModule_Create(&module); }
