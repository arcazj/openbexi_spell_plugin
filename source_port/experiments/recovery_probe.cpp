// SPDX-License-Identifier: GPL-3.0-or-later
// Isolated feasibility experiment, NOT a released warm-start implementation.
// Private layout is intentionally restricted to one CPython build family.
#define Py_BUILD_CORE
#include <Python.h>
#include <frameobject.h>
#include "internal/pycore_frame.h"
#include <vector>
#include <cstring>
#if PY_MAJOR_VERSION != 3 || PY_MINOR_VERSION != 13 || PY_MICRO_VERSION != 14 || defined(Py_GIL_DISABLED)
#error "Recovery experiment requires GIL-enabled CPython 3.13.14"
#endif

struct Ref {
    PyObject* value;
    explicit Ref(PyObject* p = nullptr): value(p) {}
    ~Ref() { Py_XDECREF(value); }
    Ref(const Ref&) = delete;
};
struct TraceScope {
    Py_tracefunc previous;
    Ref object;
    TraceScope(Py_tracefunc callback, PyObject* capsule):
        previous(PyThreadState_Get()->c_tracefunc), object(Py_XNewRef(PyThreadState_Get()->c_traceobj)) {
        PyEval_SetTrace(callback, capsule);
    }
    ~TraceScope() { PyEval_SetTrace(previous, object.value); }
};
struct Snapshot {
    PyCodeObject* code = nullptr;
    PyObject* globals = nullptr;
    PyObject* locals = nullptr;
    PyObject* handled = nullptr;
    std::vector<PyObject*> slots;
    int offset = -1;
    ~Snapshot() {
        for (PyObject* p: slots) Py_XDECREF(p);
        Py_XDECREF(code); Py_XDECREF(globals); Py_XDECREF(locals); Py_XDECREF(handled);
    }
};
struct Capture {
    PyCodeObject* subject;
    PyObject* stop;
    int line, occurrence, visits = 0;
    Snapshot* snapshot = nullptr;
    PyObject* callback = nullptr; // borrowed for the duration of capture()
    ~Capture() { delete snapshot; }
};
static PyObject* snapshot_state(Snapshot* s) {
    Ref slots(PyTuple_New(s->slots.size()));
    Ref nulls(PyBytes_FromStringAndSize(nullptr, s->slots.size()));
    if (!slots.value || !nulls.value) return nullptr;
    for (size_t i=0; i<s->slots.size(); ++i) {
        PyTuple_SET_ITEM(slots.value, i, Py_NewRef(s->slots[i] ? s->slots[i] : Py_None));
        PyBytes_AS_STRING(nulls.value)[i] = s->slots[i] ? 0 : 1;
    }
    return Py_BuildValue("(OOOOOOi)", s->code, s->globals, s->locals,
        s->handled ? s->handled : Py_None, slots.value, nulls.value, s->offset);
}
static int capture_trace(PyObject* capsule, PyFrameObject* frame, int event, PyObject*) {
    auto* state = static_cast<Capture*>(PyCapsule_GetPointer(capsule, "probe.capture"));
    if (!state) return -1;
    if (event != PyTrace_LINE || _PyFrame_GetCode(frame->f_frame) != state->subject
            || PyFrame_GetLineNumber(frame) != state->line || state->snapshot) return 0;
    if (++state->visits != state->occurrence) return 0;
    auto* f = frame->f_frame;
    auto* code = state->subject;
    if (f->stacktop < code->co_nlocalsplus || f->stacktop > code->co_nlocalsplus + code->co_stacksize) {
        PyErr_SetString(PyExc_RuntimeError, "stack pointer unavailable at checkpoint"); return -1;
    }
    auto* snapshot = new Snapshot();
    state->snapshot = snapshot;
    snapshot->code = reinterpret_cast<PyCodeObject*>(Py_NewRef(code));
    snapshot->globals = state->callback ? Py_NewRef(f->f_globals) : PyDict_Copy(f->f_globals);
    Ref locals(PyFrame_GetLocals(frame));
    if (!snapshot->globals || !locals.value) return -1;
    snapshot->locals = locals.value == f->f_globals ? Py_NewRef(snapshot->globals) : PyObject_CallOneArg(reinterpret_cast<PyObject*>(&PyDict_Type), locals.value);
    if (!snapshot->locals) return -1;
    snapshot->handled = PyErr_GetHandledException();
    snapshot->offset = static_cast<int>(f->instr_ptr - _PyCode_CODE(code));
    for (int i = 0; i < f->stacktop; ++i) snapshot->slots.push_back(Py_XNewRef(f->localsplus[i]));
    if (state->callback) {
        Ref saved(snapshot_state(snapshot));
        if (!saved.value) return -1;
        Ref result(PyObject_CallOneArg(state->callback, saved.value));
        if (!result.value) return -1;
    }
    PyErr_SetNone(state->stop);
    return -1;
}
static void release_snapshot(PyObject* capsule) {
    delete static_cast<Snapshot*>(PyCapsule_GetPointer(capsule, "probe.snapshot"));
}
static PyObject* capture(PyObject*, PyObject* args) {
    PyObject *program, *subject, *globals, *callback = Py_None;
    int line, occurrence = 1;
    if (!PyArg_ParseTuple(args, "OOOi|iO", &program, &subject, &globals, &line, &occurrence, &callback)) return nullptr;
    if (!PyCode_Check(program) || !PyCode_Check(subject) || !PyDict_Check(globals) || occurrence < 1) {
        PyErr_SetString(PyExc_TypeError, "invalid capture inputs"); return nullptr;
    }
    Ref stop(PyErr_NewException("_recovery_probe.CheckpointStop", PyExc_BaseException, nullptr));
    if (!stop.value) return nullptr;
    Capture state{reinterpret_cast<PyCodeObject*>(subject), stop.value, line, occurrence};
    if (callback != Py_None) {
        if (!PyCallable_Check(callback)) { PyErr_SetString(PyExc_TypeError, "callback must be callable"); return nullptr; }
        state.callback = callback;
    }
    Ref capsule(PyCapsule_New(&state, "probe.capture", nullptr));
    if (!capsule.value) return nullptr;
    TraceScope trace(capture_trace, capsule.value);
    Ref result(PyEval_EvalCode(program, globals, globals));
    if (!PyErr_ExceptionMatches(stop.value)) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError, "checkpoint not reached or stop intercepted");
        return nullptr;
    }
    PyErr_Clear();
    PyObject* snapshot = PyCapsule_New(state.snapshot, "probe.snapshot", release_snapshot);
    if (snapshot) state.snapshot = nullptr;
    return snapshot;
}
struct Restore { Snapshot* snapshot; bool applied = false; };
static int restore_trace(PyObject* capsule, PyFrameObject* frame, int event, PyObject*) {
    auto* state = static_cast<Restore*>(PyCapsule_GetPointer(capsule, "probe.restore"));
    if (!state) return -1;
    Snapshot* s = state->snapshot;
    auto* f = frame->f_frame;
    if (event != PyTrace_LINE || _PyFrame_GetCode(f) != s->code || state->applied) return 0;
    if (f->owner != FRAME_OWNED_BY_THREAD || f->stacktop < 0
            || s->slots.size() > static_cast<size_t>(s->code->co_nlocalsplus + s->code->co_stacksize)) {
        PyErr_SetString(PyExc_RuntimeError, "invalid restoration frame"); return -1;
    }
    // CPython allocated the live frame; preserve its ownership and call chain.
    // Only the private operand/local slots and instruction cursor are restored.
    for (int i = 0; i < f->stacktop; ++i) Py_CLEAR(f->localsplus[i]);
    for (size_t i = 0; i < s->slots.size(); ++i) f->localsplus[i] = Py_XNewRef(s->slots[i]);
    f->stacktop = static_cast<int>(s->slots.size());
    f->instr_ptr = _PyCode_CODE(s->code) + s->offset;
    frame->f_lineno = 0;
    PyErr_SetHandledException(s->handled);
    state->applied = true;
    return 0;
}
static PyObject* resume(PyObject*, PyObject* capsule) {
    auto* snapshot = static_cast<Snapshot*>(PyCapsule_GetPointer(capsule, "probe.snapshot"));
    if (!snapshot) return nullptr;
    auto* code = snapshot->code;
    if (code->co_argcount || code->co_kwonlyargcount || code->co_nfreevars
            || (code->co_flags & (CO_VARARGS | CO_VARKEYWORDS | CO_GENERATOR | CO_COROUTINE | CO_ASYNC_GENERATOR))) {
        PyErr_SetString(PyExc_NotImplementedError, "probe supports only synchronous, argument-free code without free variables"); return nullptr;
    }
    Restore state{snapshot};
    Ref trace(PyCapsule_New(&state, "probe.restore", nullptr));
    if (!trace.value) return nullptr;
    Ref previous(PyErr_GetHandledException());
    TraceScope tracing(restore_trace, trace.value);
    Ref result(PyEval_EvalCode(reinterpret_cast<PyObject*>(code), snapshot->globals, snapshot->locals));
    PyErr_SetHandledException(previous.value);
    if (!result.value) return nullptr;
    if (!state.applied) { PyErr_SetString(PyExc_RuntimeError, "restoration trace not reached"); return nullptr; }
    return Py_BuildValue("(OOii)", result.value, snapshot->globals, snapshot->offset, static_cast<int>(snapshot->slots.size()));
}
static PyObject* from_state(PyObject*, PyObject* value) {
    PyObject *code, *globals, *locals, *handled, *slots, *nulls;
    int offset;
    if (!PyTuple_Check(value)) { PyErr_SetString(PyExc_TypeError, "expected snapshot tuple"); return nullptr; }
    if (!PyArg_ParseTuple(value, "OOOOOOi", &code, &globals,
            &locals, &handled, &slots, &nulls, &offset)) return nullptr;
    if (!PyCode_Check(code) || !PyDict_Check(globals) || !PyDict_Check(locals)
            || (handled != Py_None && !PyExceptionInstance_Check(handled))
            || !PyTuple_Check(slots) || !PyBytes_Check(nulls)) {
        PyErr_SetString(PyExc_TypeError, "invalid snapshot field types"); return nullptr;
    }
    auto* co = reinterpret_cast<PyCodeObject*>(code);
    Ref bytecode(PyCode_GetCode(co));
    if (!bytecode.value) return nullptr;
    Py_ssize_t count = PyTuple_GET_SIZE(slots);
    if (count < co->co_nlocalsplus || count > co->co_nlocalsplus + co->co_stacksize
            || PyBytes_GET_SIZE(nulls) != count || offset < 0
            || offset >= PyBytes_GET_SIZE(bytecode.value)/static_cast<int>(sizeof(_Py_CODEUNIT))) {
        PyErr_SetString(PyExc_ValueError, "invalid snapshot extent"); return nullptr;
    }
    for (Py_ssize_t i=0; i<count; ++i) {
        char flag = PyBytes_AS_STRING(nulls)[i];
        if (flag != 0 && flag != 1) { PyErr_SetString(PyExc_ValueError, "invalid null-slot flag"); return nullptr; }
    }
    auto* s = new Snapshot();
    s->code = reinterpret_cast<PyCodeObject*>(Py_NewRef(code));
    s->globals = Py_NewRef(globals); s->locals = Py_NewRef(locals);
    s->handled = handled == Py_None ? nullptr : Py_NewRef(handled);
    s->offset = offset;
    for (Py_ssize_t i=0; i<count; ++i)
        s->slots.push_back(PyBytes_AS_STRING(nulls)[i] ? nullptr : Py_NewRef(PyTuple_GET_ITEM(slots, i)));
    PyObject* capsule = PyCapsule_New(s, "probe.snapshot", release_snapshot);
    if (!capsule) delete s;
    return capsule;
}
static PyMethodDef methods[] = {
    {"from_state", from_state, METH_O, nullptr},
    {"capture", capture, METH_VARARGS, nullptr},
    {"resume", resume, METH_O, nullptr},
    {nullptr, nullptr, 0, nullptr}
};
static PyModuleDef module = {PyModuleDef_HEAD_INIT, "_recovery_probe", nullptr, -1, methods};
PyMODINIT_FUNC PyInit__recovery_probe() {
    if (std::strncmp(Py_GetVersion(), "3.13.14 ", 8) != 0) {
        PyErr_SetString(PyExc_ImportError, "recovery experiment ABI mismatch"); return nullptr;
    }
    return PyModule_Create(&module);
}
