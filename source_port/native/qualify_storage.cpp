// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_WS/SPELLwsStorage.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_UTIL/SPELLerror.H"

static PyObject* fail(const SPELLcoreException& e) {
    PyErr_SetString(PyExc_RuntimeError, (e.getError() + ": " + e.getReason()).c_str());
    return nullptr;
}
static void destroy(PyObject* capsule) {
    delete static_cast<SPELLwsStorage*>(PyCapsule_GetPointer(capsule, "SPELL.storage"));
}
static SPELLwsStorage* storage(PyObject* capsule) {
    return static_cast<SPELLwsStorage*>(PyCapsule_GetPointer(capsule, "SPELL.storage"));
}
static PyObject* create(PyObject*, PyObject* args) {
    const char* path;
    int mode;
    if (!PyArg_ParseTuple(args, "si", &path, &mode)) return nullptr;
    if (mode != 0 && mode != 1) { PyErr_SetString(PyExc_ValueError, "mode must be read=0 or write=1"); return nullptr; }
    try {
        auto* instance = new SPELLwsStorage(path, static_cast<SPELLwsStorage::Mode>(mode));
        PyObject* capsule = PyCapsule_New(instance, "SPELL.storage", destroy);
        if (!capsule) delete instance;
        return capsule;
    } catch (const SPELLcoreException& e) { return fail(e); }
}
static PyObject* store(PyObject*, PyObject* args) {
    PyObject *capsule, *value;
    if (!PyArg_ParseTuple(args, "OO", &capsule, &value)) return nullptr;
    auto* instance = storage(capsule);
    if (!instance) return nullptr;
    try { instance->storeObject(value); }
    catch (const SPELLcoreException& e) { return fail(e); }
    Py_RETURN_NONE;
}
static PyObject* store_none(PyObject*, PyObject* capsule) {
    auto* instance = storage(capsule);
    if (!instance) return nullptr;
    try { instance->storeObjectOrNone(nullptr); }
    catch (const SPELLcoreException& e) { return fail(e); }
    Py_RETURN_NONE;
}
static PyObject* load(PyObject*, PyObject* capsule) {
    auto* instance = storage(capsule);
    if (!instance) return nullptr;
    try { return instance->loadObject(); }
    catch (const SPELLcoreException& e) { return fail(e); }
}
static PyObject* load_long(PyObject*, PyObject* capsule) {
    auto* instance = storage(capsule);
    if (!instance) return nullptr;
    try { return PyLong_FromLong(instance->loadLong()); }
    catch (const SPELLcoreException& e) { return fail(e); }
}
static PyObject* store_long(PyObject*, PyObject* args) {
    PyObject* capsule;
    long number;
    if (!PyArg_ParseTuple(args, "Ol", &capsule, &number)) return nullptr;
    auto* instance = storage(capsule);
    if (!instance) return nullptr;
    try { instance->storeLong(number); }
    catch (const SPELLcoreException& e) { return fail(e); }
    Py_RETURN_NONE;
}
static PyObject* reset(PyObject*, PyObject* args) {
    PyObject* capsule;
    int mode;
    if (!PyArg_ParseTuple(args, "Oi", &capsule, &mode)) return nullptr;
    auto* instance = storage(capsule);
    if (!instance) return nullptr;
    if (mode != 0 && mode != 1) { PyErr_SetString(PyExc_ValueError, "invalid mode"); return nullptr; }
    try { instance->reset(static_cast<SPELLwsStorage::Mode>(mode)); }
    catch (const SPELLcoreException& e) { return fail(e); }
    Py_RETURN_NONE;
}
static PyMethodDef methods[] = {
    {"create", create, METH_VARARGS, nullptr}, {"store", store, METH_VARARGS, nullptr},
    {"store_none", store_none, METH_O, nullptr}, {"load", load, METH_O, nullptr},
    {"store_long", store_long, METH_VARARGS, nullptr}, {"load_long", load_long, METH_O, nullptr},
    {"reset", reset, METH_VARARGS, nullptr}, {nullptr, nullptr, 0, nullptr}
};
static PyModuleDef module = {PyModuleDef_HEAD_INIT, "_spell_storage_qualification", nullptr, -1, methods};
PyMODINIT_FUNC PyInit__spell_storage_qualification() { return PyModule_Create(&module); }
