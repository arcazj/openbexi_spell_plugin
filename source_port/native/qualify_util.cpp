// SPDX-License-Identifier: GPL-3.0-or-later
// Qualification adapter: calls original, patched SPELL utilities directly.
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include "SPELL_UTIL/SPELLpythonMonitors.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include <thread>
#include <stdexcept>

static PyObject* error_result(const SPELLcoreException& error) {
    return Py_BuildValue("(iss)", static_cast<int>(error.getCode()),
        error.getError().c_str(), error.getReason().c_str());
}
static PyObject* compile_source(PyObject*, PyObject* source) {
    Py_ssize_t size;
    const char* data = PyUnicode_AsUTF8AndSize(source, &size);
    if (!data) return nullptr;
    try {
        return reinterpret_cast<PyObject*>(SPELLpythonHelper::instance().compileScript(std::string(data, size)));
    } catch (const SPELLcoreException& error) { return error_result(error); }
}
static PyObject* compile_file(PyObject*, PyObject* name) {
    const char* filename = PyUnicode_AsUTF8(name);
    if (!filename) return nullptr;
    try {
        return reinterpret_cast<PyObject*>(SPELLpythonHelper::instance().compile(filename));
    } catch (const SPELLcoreException& error) { return error_result(error); }
}
static PyObject* line_jump(PyObject*, PyObject* args) {
    PyObject* frame;
    int line;
    if (!PyArg_ParseTuple(args, "Oi", &frame, &line)) return nullptr;
    if (!PyFrame_Check(frame)) {
        PyErr_SetString(PyExc_TypeError, "expected a frame"); return nullptr;
    }
    try {
        SPELLpythonHelper::instance().setNewLine(reinterpret_cast<PyFrameObject*>(frame), line, -1);
        Py_RETURN_NONE;
    } catch (const SPELLcoreException& error) { return error_result(error); }
}
static PyObject* scope_error(PyObject*, PyObject* callback) {
    try {
        SPELLsafePythonOperations monitor("qualification");
        SPELLpython313::Owned result(PyObject_CallNoArgs(callback));
    } catch (const SPELLcoreException& error) { return error_result(error); }
    Py_RETURN_NONE;
}
static PyObject* native_thread_errors(PyObject*, PyObject*) {
    int converted = 0;
    bool balanced = true;
    std::thread worker([&] {
        for (int n = 0; n < 200; ++n) {
            try {
                SPELLsafePythonOperations monitor("native worker");
                PyErr_SetString(PyExc_ValueError, "worker error");
            } catch (const SPELLcoreException& error) {
                if (error.getCode() == SPELL_PYERROR_VALUE) ++converted;
            }
            if (PyGILState_Check()) balanced = false;
        }
    });
    Py_BEGIN_ALLOW_THREADS
    worker.join();
    Py_END_ALLOW_THREADS
    return Py_BuildValue("(iO)", converted, balanced ? Py_True : Py_False);
}
static PyObject* lifecycle(PyObject*, PyObject*) {
    auto& helper = SPELLpythonHelper::instance();
    helper.initialize();
    bool initialized = helper.isInitialized();
    helper.finalize();
    return Py_BuildValue("(OO)", initialized ? Py_True : Py_False,
        Py_IsInitialized() ? Py_True : Py_False);
}
static PyObject* add_path(PyObject*, PyObject* path) {
    const char* data = PyUnicode_AsUTF8(path);
    if (!data) return nullptr;
    try { SPELLpythonHelper::instance().addToPath(data); }
    catch (const SPELLcoreException& error) { return error_result(error); }
    Py_RETURN_NONE;
}
static PyObject* make_instance(PyObject*, PyObject* args) {
    PyObject* cls;
    PyObject* positional;
    PyObject* keywords;
    if (!PyArg_ParseTuple(args, "OOO", &cls, &positional, &keywords)) return nullptr;
    try {
        return SPELLpythonHelper::instance().newInstance(cls,
            positional == Py_None ? nullptr : positional,
            keywords == Py_None ? nullptr : keywords);
    } catch (const SPELLcoreException& error) { return error_result(error); }
}
static PyObject* dump_state(PyObject*, PyObject*) {
    SPELLutils::dumpInterpreterInfo("qualification");
    Py_RETURN_NONE;
}
static PyObject* control(PyObject*, PyObject* terminate) {
    auto& errors = SPELLerror::instance();
    errors.clearErrors();
    if (terminate == Py_True) errors.setExecutionTerminated();
    else errors.setExecutionAborted();
    bool state = terminate == Py_True ? errors.isExecutionTerminated() : errors.isExecutionAborted();
    PyObject* result = Py_BuildValue("(OO)", state ? Py_True : Py_False,
        PyErr_Occurred() ? Py_True : Py_False);
    errors.clearErrors();
    return result;
}
struct TraceState { PyCodeObject* code; int from; int to; int count; };
static int trace_jump(PyObject* capsule, PyFrameObject* frame, int event, PyObject*) {
    auto* state = static_cast<TraceState*>(PyCapsule_GetPointer(capsule, "SPELL.test.trace"));
    if (!state) return -1;
    SPELLpython313::Owned code(reinterpret_cast<PyObject*>(PyFrame_GetCode(frame)));
    if (event == PyTrace_LINE && code.get() == reinterpret_cast<PyObject*>(state->code)
        && PyFrame_GetLineNumber(frame) == state->from && state->count == 0) {
        ++state->count;
        try { SPELLpythonHelper::instance().setNewLine(frame, state->to, -1); }
        catch (const SPELLcoreException& error) {
            PyErr_SetString(PyExc_RuntimeError, error.what().c_str());
            return -1;
        }
    }
    return 0;
}
static PyObject* native_trace(PyObject*, PyObject* args) {
    PyObject* code;
    int from, to;
    if (!PyArg_ParseTuple(args, "Oii", &code, &from, &to)) return nullptr;
    if (!PyCode_Check(code)) { PyErr_SetString(PyExc_TypeError, "expected code"); return nullptr; }
    TraceState state{reinterpret_cast<PyCodeObject*>(code), from, to, 0};
    SPELLpython313::Owned capsule(PyCapsule_New(&state, "SPELL.test.trace", nullptr));
    SPELLpython313::Owned globals(PyDict_New());
    if (!capsule.get() || !globals.get()) return nullptr;
    PyDict_SetItemString(globals.get(), "__builtins__", PyEval_GetBuiltins());
    PyEval_SetTrace(trace_jump, capsule.get());
    SPELLpython313::Owned result(PyEval_EvalCode(code, globals.get(), globals.get()));
    PyEval_SetTrace(nullptr, nullptr);
    if (!result.get()) return nullptr;
    PyObject* answer = PyDict_GetItemString(globals.get(), "result");
    if (!answer) { PyErr_SetString(PyExc_KeyError, "result"); return nullptr; }
    return Py_BuildValue("(Oi)", answer, state.count);
}
static PyObject* frame_metadata(PyObject*, PyObject* object) {
    if (!PyFrame_Check(object)) { PyErr_SetString(PyExc_TypeError, "expected a frame"); return nullptr; }
    auto* frame = reinterpret_cast<PyFrameObject*>(object);
    SPELLpython313::FrameCode code(frame);
    std::string filename = SPELLpython313::filename(frame);
    std::string name = SPELLpython313::codename(frame);
    return Py_BuildValue("(Ossii)", code.get(), filename.c_str(), name.c_str(),
        PyFrame_GetLineNumber(frame), PyFrame_GetLasti(frame));
}
static PyObject* make_frame(PyObject*, PyObject* args) {
    const char* name;
    PyObject* value;
    int function;
    if (!PyArg_ParseTuple(args, "sOp", &name, &value, &function)) return nullptr;
    try {
        auto& helper = SPELLpythonHelper::instance();
        if (!function && !PyCode_Check(value)) { PyErr_SetString(PyExc_TypeError, "expected code"); return nullptr; }
        return reinterpret_cast<PyObject*>(function ? helper.createFrameFromFunction(name, value)
            : helper.createFrame(name, reinterpret_cast<PyCodeObject*>(value)));
    } catch (const SPELLcoreException& error) {
        PyErr_SetString(PyExc_RuntimeError, error.what().c_str()); return nullptr;
    }
}
static PyMethodDef methods[] = {
    {"make_frame", make_frame, METH_VARARGS, nullptr},
    {"frame_metadata", frame_metadata, METH_O, nullptr},
    {"compile", compile_source, METH_O, nullptr},
    {"compile_file", compile_file, METH_O, nullptr},
    {"jump", line_jump, METH_VARARGS, nullptr},
    {"scope", scope_error, METH_O, nullptr},
    {"thread_errors", native_thread_errors, METH_NOARGS, nullptr},
    {"lifecycle", lifecycle, METH_NOARGS, nullptr},
    {"add_path", add_path, METH_O, nullptr},
    {"new_instance", make_instance, METH_VARARGS, nullptr},
    {"dump_state", dump_state, METH_NOARGS, nullptr},
    {"control", control, METH_O, nullptr},
    {"native_trace", native_trace, METH_VARARGS, nullptr},
    {nullptr, nullptr, 0, nullptr}
};
static PyModuleDef module = {PyModuleDef_HEAD_INIT, "_spell_util_qualification", nullptr, -1, methods};
PyMODINIT_FUNC PyInit__spell_util_qualification() { return PyModule_Create(&module); }
