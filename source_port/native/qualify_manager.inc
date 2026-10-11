// SPDX-License-Identifier: GPL-3.0-or-later
// Component adapter: calls the original public manager methods. Notifications
// are disabled using the original configuration flags, not mocked CIF services.
#include "SPELL_EXC/SPELLframeManager.H"
#include "SPELL_WS/SPELLwsWarmStartImpl.H"
namespace {
struct QuietMonitors {
    bool watch = SPELLvariableMonitor::s_enabled, resources = SPELLresourceMonitor::s_enabled;
    QuietMonitors() { SPELLvariableMonitor::s_enabled = false; SPELLresourceMonitor::s_enabled = false; }
    ~QuietMonitors() { SPELLvariableMonitor::s_enabled = watch; SPELLresourceMonitor::s_enabled = resources; }
};
struct ManagerHandle { std::unique_ptr<SPELLframeManager> manager; };
void destroy_manager(PyObject* capsule) {
    delete static_cast<ManagerHandle*>(PyCapsule_GetPointer(capsule, "SPELL.manager"));
}
ManagerHandle* manager_handle(PyObject* capsule) {
    auto* handle = static_cast<ManagerHandle*>(PyCapsule_GetPointer(capsule, "SPELL.manager"));
    if (handle && !handle->manager) { PyErr_SetString(PyExc_ValueError, "manager is closed"); return nullptr; }
    return handle;
}
PyObject* manager_create(PyObject*, PyObject* object) {
    if (object != Py_None && !PyFrame_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "expected frame or None"); return nullptr;
    }
    QuietMonitors quiet;
    auto handle = std::make_unique<ManagerHandle>();
    try {
        handle->manager = std::make_unique<SPELLframeManager>();
        if (object != Py_None) {
            auto* frame = reinterpret_cast<PyFrameObject*>(object);
            handle->manager->callbackEventCall(frame, SPELLpython313::filename(frame),
                PyFrame_GetLineNumber(frame), SPELLpython313::codename(frame));
        }
        PyObject* capsule = PyCapsule_New(handle.get(), "SPELL.manager", destroy_manager);
        if (capsule) handle.release();
        return capsule;
    } catch (const SPELLcoreException& e) { return failure(e); }
}
PyObject* manager_close(PyObject*, PyObject* capsule) {
    auto* handle = manager_handle(capsule); if (!handle) return nullptr;
    handle->manager.reset(); Py_RETURN_NONE;
}
PyObject* manager_script(PyObject*, PyObject* args) {
    PyObject* capsule; const char* source;
    if (!PyArg_ParseTuple(args, "Os", &capsule, &source)) return nullptr;
    auto* handle = manager_handle(capsule); if (!handle) return nullptr;
    QuietMonitors quiet;
    try { handle->manager->runScript(source); }
    catch (const SPELLcoreException& e) { return failure(e); }
    Py_RETURN_NONE;
}
PyObject* manager_event(PyObject*, PyObject* args) {
    PyObject *capsule, *object; int event;
    if (!PyArg_ParseTuple(args, "OOi", &capsule, &object, &event)) return nullptr;
    auto* handle = manager_handle(capsule); if (!handle) return nullptr;
    if (!PyFrame_Check(object)) { PyErr_SetString(PyExc_TypeError, "expected frame"); return nullptr; }
    auto* frame = reinterpret_cast<PyFrameObject*>(object);
    QuietMonitors quiet;
    try {
        auto file = SPELLpython313::filename(frame), name = SPELLpython313::codename(frame);
        int line = PyFrame_GetLineNumber(frame);
        if (event == PyTrace_CALL) {
            handle->manager->updateCurrentFrame(frame, event);
            handle->manager->callbackEventCall(frame, file, line, name);
        } else if (event == PyTrace_RETURN) handle->manager->callbackEventReturn(frame, file, line, name);
        else if (event == PyTrace_LINE) handle->manager->callbackEventLine(frame, file, line, name);
        else { PyErr_SetString(PyExc_ValueError, "unsupported event"); return nullptr; }
    } catch (const SPELLcoreException& e) { return failure(e); }
    Py_RETURN_NONE;
}
PyObject* manager_copy(PyObject*, PyObject* args) {
    PyObject *capsule, *object;
    if (!PyArg_ParseTuple(args, "OO", &capsule, &object)) return nullptr;
    auto* handle = manager_handle(capsule); if (!handle) return nullptr;
    if (!PyFrame_Check(object)) { PyErr_SetString(PyExc_TypeError, "expected frame"); return nullptr; }
    try { handle->manager->updateCurrentFrame(reinterpret_cast<PyFrameObject*>(object), PyTrace_CALL); }
    catch (const SPELLcoreException& e) { return failure(e); }
    Py_RETURN_NONE;
}
PyObject* manager_definitions(PyObject*, PyObject* capsule) {
    auto* handle = manager_handle(capsule); if (!handle) return nullptr;
    try { handle->manager->filterDictUpdated(); }
    catch (const SPELLcoreException& e) { return failure(e); }
    Py_RETURN_NONE;
}
PyObject* ws_filter_set(PyObject*, PyObject* keys) {
    try { SPELLwsWarmStartImpl::setGlobalsFilter(keys == Py_None ? nullptr : keys); }
    catch (const SPELLcoreException& e) { return failure(e); }
    Py_RETURN_NONE;
}
PyObject* ws_filter_test(PyObject*, PyObject* args) {
    PyObject *key, *value;
    if (!PyArg_ParseTuple(args, "OO", &key, &value)) return nullptr;
    try { return PyBool_FromLong(SPELLwsWarmStartImpl::shouldFilter(key, value)); }
    catch (const SPELLcoreException& e) { return failure(e); }
}
}
