// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_WS/SPELLwsFrame.H"
#include "SPELL_WS/SPELLcontinuation313.H"
namespace {
struct WSFrameHandle { std::unique_ptr<SPELLwsFrame> frame; };
void destroy_ws_frame(PyObject* capsule) { delete static_cast<WSFrameHandle*>(PyCapsule_GetPointer(capsule,"SPELL.ws.frame")); }
WSFrameHandle* ws_frame_handle(PyObject* capsule) {
    auto* handle = static_cast<WSFrameHandle*>(PyCapsule_GetPointer(capsule,"SPELL.ws.frame"));
    if (handle && !handle->frame) { PyErr_SetString(PyExc_ValueError,"frame is closed"); return nullptr; }
    return handle;
}
PyObject* ws_frame_create(PyObject*,PyObject* args) {
    PyObject* frame; const char *procedure, *persistent = "", *recovery = "";
    if (!PyArg_ParseTuple(args,"Os|ss",&frame,&procedure,&persistent,&recovery)) return nullptr;
    if (frame != Py_None && !PyFrame_Check(frame)) { PyErr_SetString(PyExc_TypeError,"expected frame or None"); return nullptr; }
    SPELLwsStartupInfo info;
    info.procedureFile=procedure; info.persistentFile=persistent; info.recoveryFile=recovery;
    info.performRecovery=info.recoveryFile != "";
    auto handle=std::make_unique<WSFrameHandle>();
    try {
        handle->frame=std::make_unique<SPELLwsFrame>("qualified-frame",info,0,
            frame == Py_None ? nullptr : reinterpret_cast<PyFrameObject*>(frame));
        PyObject* result=PyCapsule_New(handle.get(),"SPELL.ws.frame",destroy_ws_frame);
        if (result) handle.release();
        return result;
    } catch (const SPELLcoreException& e) { return failure(e); }
}
PyObject* ws_frame_event(PyObject*,PyObject* args) {
    PyObject* capsule; const char* action;
    if (!PyArg_ParseTuple(args,"Os",&capsule,&action)) return nullptr;
    auto* h=ws_frame_handle(capsule); if (!h) return nullptr;
    try {
        std::string name(action);
        if (name=="line") h->frame->eventLine();
        else if (name=="refresh") h->frame->refresh();
        else if (name=="save") h->frame->saveState();
        else if (name=="fix") h->frame->fixState(nullptr,true);
        else if (name=="reset") h->frame->reset();
        else if (name=="cleanup") h->frame->cleanup();
        else if (name=="close") h->frame.reset();
        else { PyErr_SetString(PyExc_ValueError,"unknown frame action"); return nullptr; }
    } catch (const SPELLcoreException& e) { return failure(e); }
    Py_RETURN_NONE;
}
PyObject* ws_frame_state(PyObject*,PyObject* capsule) {
    auto* h=ws_frame_handle(capsule); if (!h) return nullptr;
    return Py_NewRef(h->frame->getState() ? h->frame->getState() : Py_None);
}
PyObject* ws_frame_view(PyObject*,PyObject* capsule) {
    auto* h=ws_frame_handle(capsule); if (!h) return nullptr;
    return Py_NewRef(h->frame->getFrameObject());
}
PyObject* ws_frame_resume(PyObject*,PyObject* capsule) {
    auto* h=ws_frame_handle(capsule); if (!h) return nullptr;
    if (!h->frame->getState()) { PyErr_SetString(PyExc_ValueError,"no saved state"); return nullptr; }
    return SPELLcontinuation313::resume(h->frame->getState());
}
PyObject* ws_frame_set(PyObject*,PyObject* args) {
    PyObject *capsule,*state;
    if (!PyArg_ParseTuple(args,"OO",&capsule,&state)) return nullptr;
    auto* h=ws_frame_handle(capsule); if (!h) return nullptr;
    try { h->frame->setState(state); }
    catch (const SPELLcoreException& e) { return failure(e); }
    Py_RETURN_NONE;
}
PyObject* ws_frame_rebind(PyObject*,PyObject* args) {
    PyObject *capsule,*frame;
    if (!PyArg_ParseTuple(args,"OO",&capsule,&frame)) return nullptr;
    auto* h=ws_frame_handle(capsule); if (!h) return nullptr;
    if (!PyFrame_Check(frame)) { PyErr_SetString(PyExc_TypeError,"expected frame"); return nullptr; }
    h->frame->rebind(reinterpret_cast<PyFrameObject*>(frame));
    Py_RETURN_NONE;
}
}
