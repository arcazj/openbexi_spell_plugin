// SPDX-License-Identifier: GPL-3.0-or-later
// Shared exact-build continuation engine for the original WS port and its probes.
// Private layout is intentionally restricted to one CPython build family.
#define Py_BUILD_CORE
#include <Python.h>
#include <frameobject.h>
#include "internal/pycore_frame.h"
#include "internal/pycore_code.h"
#include <vector>
#include <cstring>
#include <memory>
#include <unordered_map>
#if PY_MAJOR_VERSION != 3 || PY_MINOR_VERSION != 13 || PY_MICRO_VERSION != 15 || defined(Py_GIL_DISABLED)
#error "Recovery experiment requires GIL-enabled CPython 3.13.15"
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
    PyCodeObject* root = nullptr;
    bool chain = false, inRoot = false;
    std::unordered_map<PyFrameObject*,PyObject*> handled;
    ~Capture() {
        delete snapshot;
        for (auto& entry: handled) Py_XDECREF(entry.second);
    }
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
static Snapshot* copy_frame(PyFrameObject* frame, bool live_globals, PyObject* handled) {
    auto* f = frame->f_frame;
    auto* code = _PyFrame_GetCode(f);
    if (f->owner != FRAME_OWNED_BY_THREAD || (code->co_flags & (CO_GENERATOR | CO_COROUTINE | CO_ASYNC_GENERATOR))) {
        PyErr_SetString(PyExc_NotImplementedError, "checkpoint requires a synchronous thread-owned frame"); return nullptr;
    }
    if (f->stacktop < code->co_nlocalsplus || f->stacktop > code->co_nlocalsplus + code->co_stacksize) {
        PyErr_SetString(PyExc_RuntimeError, "stack pointer unavailable at checkpoint"); return nullptr;
    }
    auto snapshot = std::make_unique<Snapshot>();
    snapshot->code = reinterpret_cast<PyCodeObject*>(Py_NewRef(code));
    snapshot->globals = live_globals ? Py_NewRef(f->f_globals) : PyDict_Copy(f->f_globals);
    Ref locals(PyFrame_GetLocals(frame));
    if (!snapshot->globals || !locals.value) return nullptr;
    snapshot->locals = locals.value == f->f_globals ? Py_NewRef(snapshot->globals) : PyObject_CallOneArg(reinterpret_cast<PyObject*>(&PyDict_Type), locals.value);
    if (!snapshot->locals) return nullptr;
    snapshot->handled = Py_XNewRef(handled);
    snapshot->offset = static_cast<int>(f->instr_ptr - _PyCode_CODE(code));
    for (int i = 0; i < f->stacktop; ++i) snapshot->slots.push_back(Py_XNewRef(f->localsplus[i]));
    return snapshot.release();
}
static int capture_trace(PyObject* capsule, PyFrameObject* frame, int event, PyObject*) {
    auto* state = static_cast<Capture*>(PyCapsule_GetPointer(capsule, "probe.capture"));
    if (!state) return -1;
    if (state->chain) {
        if (event == PyTrace_CALL && _PyFrame_GetCode(frame->f_frame) == state->root) state->inRoot = true;
        if (state->inRoot && (event == PyTrace_CALL || event == PyTrace_LINE)) {
            auto& saved = state->handled[frame];
            Py_XDECREF(saved);
            saved = PyErr_GetHandledException();
            if (event == PyTrace_CALL) {
                Ref back(reinterpret_cast<PyObject*>(PyFrame_GetBack(frame)));
                auto it = state->handled.find(reinterpret_cast<PyFrameObject*>(back.value));
                if (it != state->handled.end()) {
                    Py_XDECREF(it->second);
                    it->second = PyErr_GetHandledException();
                }
            }
        }
        if (event == PyTrace_RETURN) {
            auto it = state->handled.find(frame);
            if (it != state->handled.end()) { Py_XDECREF(it->second); state->handled.erase(it); }
            if (_PyFrame_GetCode(frame->f_frame) == state->root) state->inRoot = false;
        }
    }
    if (event != PyTrace_LINE || _PyFrame_GetCode(frame->f_frame) != state->subject
            || PyFrame_GetLineNumber(frame) != state->line || state->snapshot) return 0;
    if (++state->visits != state->occurrence) return 0;
    Ref handled(PyErr_GetHandledException());
    state->snapshot = copy_frame(frame, state->callback != nullptr, handled.value);
    if (!state->snapshot) return -1;
    if (state->callback) {
        Ref saved;
        if (state->chain) {
            saved.value = PyList_New(0);
            if (!saved.value) return -1;
            Ref cursor(Py_NewRef(frame));
            _PyInterpreterFrame* child = nullptr;
            bool root_reached = false;
            while (cursor.value) {
                auto* current = reinterpret_cast<PyFrameObject*>(cursor.value);
                if (child && child->previous != current->f_frame) {
                    PyErr_SetString(PyExc_NotImplementedError, "checkpoint crosses a C-call boundary"); return -1;
                }
                auto found = state->handled.find(current);
                if (found == state->handled.end()) { PyErr_SetString(PyExc_RuntimeError, "untracked caller frame"); return -1; }
                std::unique_ptr<Snapshot> snapshot(copy_frame(current, true, found->second));
                if (!snapshot) return -1;
                int delta = current == frame ? 0 : current->f_frame->return_offset;
                if (current != frame && delta == 0) { PyErr_SetString(PyExc_NotImplementedError, "caller lacks a qualified return offset"); return -1; }
                Ref item(snapshot_state(snapshot.get()));
                if (!item.value) return -1;
                Ref entry(Py_BuildValue("(Oi)", item.value, delta));
                if (!entry.value || PyList_Append(saved.value, entry.value)<0) return -1;
                if (PyList_GET_SIZE(saved.value)>128) { PyErr_SetString(PyExc_ValueError, "checkpoint exceeds 128 caller frames"); return -1; }
                if (snapshot->code == state->root) { root_reached = true; break; }
                child = current->f_frame;
                PyObject* back = reinterpret_cast<PyObject*>(PyFrame_GetBack(current));
                Py_SETREF(cursor.value, back);
            }
            if (!root_reached) { PyErr_SetString(PyExc_RuntimeError, "checkpoint root frame not reached"); return -1; }
        } else saved.value = snapshot_state(state->snapshot);
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
    int chain = 0;
    if (!PyArg_ParseTuple(args, "OOOi|iOp", &program, &subject, &globals, &line, &occurrence, &callback, &chain)) return nullptr;
    if (!PyCode_Check(program) || !PyCode_Check(subject) || !PyDict_Check(globals) || occurrence < 1) {
        PyErr_SetString(PyExc_TypeError, "invalid capture inputs"); return nullptr;
    }
    Ref stop(PyErr_NewException("_recovery_probe.CheckpointStop", PyExc_BaseException, nullptr));
    if (!stop.value) return nullptr;
    Capture state{reinterpret_cast<PyCodeObject*>(subject), stop.value, line, occurrence};
    state.root = reinterpret_cast<PyCodeObject*>(program);
    state.chain = chain != 0;
    if (state.chain && callback == Py_None) { PyErr_SetString(PyExc_TypeError, "chain capture requires a callback"); return nullptr; }
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
struct Restore {
    Snapshot* snapshot;
    bool applied = false;
    Py_tracefunc observer = nullptr;
    PyObject* observerObject = nullptr; // TraceScope owns the reference.
};
static int restore_trace(PyObject* capsule, PyFrameObject* frame, int event, PyObject* arg) {
    auto* state = static_cast<Restore*>(PyCapsule_GetPointer(capsule, "probe.restore"));
    if (!state) return -1;
    Snapshot* s = state->snapshot;
    auto* f = frame->f_frame;
    if (state->applied)
        return state->observer ? state->observer(state->observerObject, frame, event, arg) : 0;
    if (event != PyTrace_LINE || _PyFrame_GetCode(f) != s->code) return 0;
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
    // The bootstrap CALL precedes restoration. Only expose the live frame once
    // its saved locals/stack/cursor are in place; then relay all real events.
    if (state->observer) {
        if (state->observer(state->observerObject, frame, PyTrace_CALL, Py_None)<0) return -1;
        return state->observer(state->observerObject, frame, PyTrace_LINE, Py_None);
    }
    return 0;
}
static PyObject* resume_snapshot(Snapshot* snapshot, bool relay = false) {
    auto* code = snapshot->code;
    if ((code->co_flags & (CO_GENERATOR | CO_COROUTINE | CO_ASYNC_GENERATOR))
            || (!(code->co_flags & CO_OPTIMIZED) && code->co_nfreevars)) {
        PyErr_SetString(PyExc_NotImplementedError, "probe supports only synchronous module/function frames"); return nullptr;
    }
    Ref function, positional, keywords;
    if (code->co_flags & CO_OPTIMIZED) {
        function.value = PyFunction_New(reinterpret_cast<PyObject*>(code), snapshot->globals);
        positional.value = PyTuple_New(code->co_argcount);
        keywords.value = PyDict_New();
        if (!function.value || !positional.value || !keywords.value) return nullptr;
        for (int i=0; i<code->co_argcount; ++i) PyTuple_SET_ITEM(positional.value, i, Py_NewRef(Py_None));
        Ref names(PyCode_GetVarnames(code));
        if (!names.value) return nullptr;
        for (int i=0; i<code->co_kwonlyargcount; ++i)
            if (PyDict_SetItem(keywords.value, PyTuple_GET_ITEM(names.value, code->co_argcount+i), Py_None)<0) return nullptr;
        if (code->co_nfreevars) {
            Ref closure(PyTuple_New(code->co_nfreevars));
            if (!closure.value) return nullptr;
            for (int i=0; i<code->co_nfreevars; ++i) {
                int index = code->co_nlocalsplus - code->co_nfreevars + i;
                PyObject* cell = snapshot->slots.at(index);
                if (!cell || !PyCell_Check(cell)) {
                    PyErr_SetString(PyExc_ValueError, "invalid saved closure cell"); return nullptr;
                }
                PyTuple_SET_ITEM(closure.value, i, Py_NewRef(cell));
            }
            if (PyFunction_SetClosure(function.value, closure.value)<0) return nullptr;
        }
    }
    Restore state{snapshot};
    if (relay) {
        state.observer = PyThreadState_Get()->c_tracefunc;
        state.observerObject = PyThreadState_Get()->c_traceobj;
    }
    Ref trace(PyCapsule_New(&state, "probe.restore", nullptr));
    if (!trace.value) return nullptr;
    Ref previous(PyErr_GetHandledException());
    TraceScope tracing(restore_trace, trace.value);
    Ref result(function.value ? PyObject_Call(function.value, positional.value, keywords.value)
        : PyEval_EvalCode(reinterpret_cast<PyObject*>(code), snapshot->globals, snapshot->locals));
    PyErr_SetHandledException(previous.value);
    if (!result.value) return nullptr;
    if (!state.applied) { PyErr_SetString(PyExc_RuntimeError, "restoration trace not reached"); return nullptr; }
    return Py_BuildValue("(OOii)", result.value, snapshot->globals, snapshot->offset, static_cast<int>(snapshot->slots.size()));
}
static PyObject* resume(PyObject*, PyObject* capsule) {
    auto* snapshot = static_cast<Snapshot*>(PyCapsule_GetPointer(capsule, "probe.snapshot"));
    return snapshot ? resume_snapshot(snapshot) : nullptr;
}
static PyObject* resume_error(PyObject*, PyObject* args) {
    PyObject *capsule, *error;
    int depth, target, lasti, relay = 0;
    if (!PyArg_ParseTuple(args, "OOiip|p", &capsule, &error, &depth, &target, &lasti, &relay)) return nullptr;
    auto* snapshot = static_cast<Snapshot*>(PyCapsule_GetPointer(capsule, "probe.snapshot"));
    if (!snapshot) return nullptr;
    if (!PyExceptionInstance_Check(error)) { PyErr_SetString(PyExc_TypeError, "expected exception instance"); return nullptr; }
    auto* code = snapshot->code;
    Ref instructions(PyCode_GetCode(code));
    if (!instructions.value) return nullptr;
    int count = code->co_nlocalsplus + depth;
    if (depth < 0 || count > static_cast<int>(snapshot->slots.size())
            || depth + 1 + lasti > code->co_stacksize || target < 0 || target % 2
            || target >= PyBytes_GET_SIZE(instructions.value)) {
        PyErr_SetString(PyExc_ValueError, "invalid exception handler extent"); return nullptr;
    }
    while (snapshot->slots.size() > static_cast<size_t>(count)) {
        Py_XDECREF(snapshot->slots.back());
        snapshot->slots.pop_back();
    }
    if (lasti) {
        PyObject* position = PyLong_FromLong(snapshot->offset);
        if (!position) return nullptr;
        snapshot->slots.push_back(position);
    }
    snapshot->slots.push_back(Py_NewRef(error));
    snapshot->offset = target / static_cast<int>(sizeof(_Py_CODEUNIT));
    return resume_snapshot(snapshot, relay != 0);
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
        if (i < co->co_nlocalsplus && (_PyLocals_GetKind(co->co_localspluskinds,i) & (CO_FAST_CELL|CO_FAST_FREE))
                && (flag || !PyCell_Check(PyTuple_GET_ITEM(slots,i)))) {
            PyErr_SetString(PyExc_ValueError,"invalid saved closure cell"); return nullptr;
        }
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
#include "SPELLcontinuation313.H"
namespace SPELLcontinuation313 {
PyObject* snapshot(PyFrameObject* frame, PyObject* handled) {
    std::unique_ptr<Snapshot> value(copy_frame(frame, true, handled));
    return value ? snapshot_state(value.get()) : nullptr;
}
PyFrameObject* inspection(PyObject* state) {
    Ref capsule(from_state(nullptr, state));
    if (!capsule.value) return nullptr;
    auto* saved = static_cast<Snapshot*>(PyCapsule_GetPointer(capsule.value, "probe.snapshot"));
    PyFrameObject* view = PyFrame_New(PyThreadState_Get(), saved->code, saved->globals, saved->locals);
    if (view) {
        auto* target = view->f_frame;
        for (int index=0; index<target->stacktop; ++index) Py_CLEAR(target->localsplus[index]);
        for (size_t index=0; index<saved->slots.size(); ++index)
            target->localsplus[index] = Py_XNewRef(saved->slots[index]);
        target->stacktop = static_cast<int>(saved->slots.size());
        target->instr_ptr = _PyCode_CODE(saved->code) + saved->offset;
        view->f_lineno = PyCode_Addr2Line(saved->code, saved->offset * sizeof(_Py_CODEUNIT));
    }
    return view; // Inspection only: it must never be passed to an evaluator.
}
int callerOffset(PyFrameObject* parent, PyFrameObject* child) {
    if (child->f_frame->previous != parent->f_frame || parent->f_frame->return_offset == 0) {
        PyErr_SetString(PyExc_NotImplementedError, "checkpoint crosses a C-call boundary"); return -1;
    }
    return parent->f_frame->return_offset;
}
PyObject* resume(PyObject* state) {
    Ref capsule(from_state(nullptr, state));
    if (!capsule.value) return nullptr;
    return resume_snapshot(static_cast<Snapshot*>(PyCapsule_GetPointer(capsule.value, "probe.snapshot")), true);
}
}
static PyObject* resume_traced(PyObject*, PyObject* capsule) {
    auto* value = static_cast<Snapshot*>(PyCapsule_GetPointer(capsule, "probe.snapshot"));
    return value ? resume_snapshot(value, true) : nullptr;
}
static PyObject* inspect_state(PyObject*, PyObject* state) {
    return reinterpret_cast<PyObject*>(SPELLcontinuation313::inspection(state));
}
static PyObject* capture_frame(PyObject*, PyObject* args) {
    PyObject *frame, *handled = Py_None;
    if (!PyArg_ParseTuple(args, "O|O", &frame, &handled)) return nullptr;
    if (!PyFrame_Check(frame) || (handled != Py_None && !PyExceptionInstance_Check(handled))) {
        PyErr_SetString(PyExc_TypeError, "expected frame and handled exception or None"); return nullptr;
    }
    return SPELLcontinuation313::snapshot(reinterpret_cast<PyFrameObject*>(frame), handled == Py_None ? nullptr : handled);
}
static PyMethodDef methods[] = {
    {"snapshot", capture_frame, METH_VARARGS, nullptr},
    {"inspection", inspect_state, METH_O, nullptr},
    {"resume_traced", resume_traced, METH_O, nullptr},
    {"from_state", from_state, METH_O, nullptr},
    {"capture", capture, METH_VARARGS, nullptr},
    {"resume", resume, METH_O, nullptr},
    {"resume_error", resume_error, METH_VARARGS, nullptr},
    {nullptr, nullptr, 0, nullptr}
};
#ifdef SPELL_RECOVERY_PROBE
#define SPELL_CONTINUATION_NAME "_recovery_probe"
#define SPELL_CONTINUATION_INIT PyInit__recovery_probe
#else
#define SPELL_CONTINUATION_NAME "_spell_continuation"
#define SPELL_CONTINUATION_INIT PyInit__spell_continuation
#endif
static PyModuleDef module = {PyModuleDef_HEAD_INIT, SPELL_CONTINUATION_NAME, nullptr, -1, methods};
PyMODINIT_FUNC SPELL_CONTINUATION_INIT() {
    if (std::strncmp(Py_GetVersion(), "3.13.15 ", 8) != 0) {
        PyErr_SetString(PyExc_ImportError, "recovery experiment ABI mismatch"); return nullptr;
    }
    return PyModule_Create(&module);
}
PyObject* SPELLcontinuation313::module() {
    PyObject* modules = PyImport_GetModuleDict();
    PyObject* existing = PyDict_GetItemString(modules,SPELL_CONTINUATION_NAME);
    if (existing) {
        if (!PyModule_Check(existing)) { PyErr_SetString(PyExc_ImportError,"invalid continuation module"); return nullptr; }
        return Py_NewRef(existing);
    }
    Ref created(SPELL_CONTINUATION_INIT());
    if (!created.value || PyDict_SetItemString(modules,SPELL_CONTINUATION_NAME,created.value)<0) return nullptr;
    return Py_NewRef(created.value);
}
