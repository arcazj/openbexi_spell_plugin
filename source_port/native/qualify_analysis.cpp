// SPDX-License-Identifier: GPL-3.0-or-later
// Qualification adapter for the actual original analyzer classes.
#include "SPELL_EXC/SPELLastAnalyzer.H"
#include "SPELL_EXC/SPELLlnotab.H"
#include "SPELL_EXC/SPELLgoto.H"
#include "SPELL_EXC/SPELLvariableMonitor.H"
#include "SPELL_EXC/SPELLbytecode.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include <array>
#include <memory>

static PyObject* failure(const SPELLcoreException& error) {
    PyErr_SetString(PyExc_RuntimeError, (error.getError() + ": " + error.getReason()).c_str());
    return nullptr;
}
static void destroy_analyzer(PyObject* capsule) {
    delete static_cast<SPELLastAnalyzer*>(PyCapsule_GetPointer(capsule, "SPELL.analysis"));
}
static PyObject* create(PyObject*, PyObject*) {
    auto* analyzer = new SPELLastAnalyzer();
    PyObject* result = PyCapsule_New(analyzer, "SPELL.analysis", destroy_analyzer);
    if (!result) delete analyzer;
    return result;
}
static PyObject* process(PyObject*, PyObject* args) {
    PyObject* capsule;
    const char* filename;
    if (!PyArg_ParseTuple(args, "Os", &capsule, &filename)) return nullptr;
    auto* analyzer = static_cast<SPELLastAnalyzer*>(PyCapsule_GetPointer(capsule, "SPELL.analysis"));
    if (!analyzer) return nullptr;
    try { analyzer->process(filename); }
    catch (const SPELLcoreException& error) { return failure(error); }
    Py_RETURN_NONE;
}
static PyObject* classify(PyObject*, PyObject* args) {
    PyObject* capsule;
    unsigned int line;
    if (!PyArg_ParseTuple(args, "OI", &capsule, &line)) return nullptr;
    auto* analyzer = static_cast<SPELLastAnalyzer*>(PyCapsule_GetPointer(capsule, "SPELL.analysis"));
    if (!analyzer) return nullptr;
    return Py_BuildValue("(iiii)", analyzer->isSimpleLine(line), analyzer->isBlockStart(line),
                         analyzer->isInsideBlock(line), analyzer->getBlockEnd(line));
}
static PyObject* lines(PyObject*, PyObject* code) {
    if (!PyCode_Check(code)) { PyErr_SetString(PyExc_TypeError, "expected code"); return nullptr; }
    try {
        auto* input = reinterpret_cast<PyCodeObject*>(code);
        SPELLlnotab analyzer(input);
        SPELLpython313::Owned rows(PyList_New(0));
        if (!rows.get()) return nullptr;
        for (int line: analyzer.getLines()) {
            int offset = analyzer.offset(line);
            SPELLpython313::Owned row(Py_BuildValue("(iiiii)", line, analyzer.lineBefore(line),
                analyzer.lineAfter(line), offset, PyCode_Addr2Line(input, offset)));
            if (!row.get() || PyList_Append(rows.get(), row.get()) < 0) return nullptr;
        }
        return Py_BuildValue("{s:O,s:i,s:(iii)}", "rows", rows.get(), "first", analyzer.getFirstLine(),
            "missing", analyzer.lineBefore(999999), analyzer.lineAfter(999999), analyzer.offset(999999));
    } catch (const SPELLcoreException& error) { return failure(error); }
}
static PyObject* goto_info(PyObject*, PyObject* args) {
    PyObject* code;
    int count;
    if (!PyArg_ParseTuple(args, "Oi", &code, &count)) return nullptr;
    if (!PyCode_Check(code) || count < 0 || count > 10000) {
        PyErr_SetString(PyExc_ValueError, "expected code and 0..10000 lines"); return nullptr;
    }
    try {
        SPELLgoto analyzer(reinterpret_cast<PyCodeObject*>(code));
        SPELLpython313::Owned labels(PyDict_New()), rows(PyList_New(0));
        if (!labels.get() || !rows.get()) return nullptr;
        for (const auto& label: analyzer.getLabels()) {
            SPELLpython313::Owned key(PyUnicode_DecodeUTF8(label.first.data(), label.first.size(), "strict"));
            SPELLpython313::Owned line(PyLong_FromUnsignedLong(label.second));
            if (!key.get() || !line.get() || PyDict_SetItem(labels.get(), key.get(), line.get()) < 0) return nullptr;
        }
        for (int n = 1; n <= count; ++n) {
            SPELLpython313::Owned row(Py_BuildValue("(iiii)", n, analyzer.isLabel(n), analyzer.isInitStep(n), analyzer.getTargetLine(n)));
            if (!row.get() || PyList_Append(rows.get(), row.get()) < 0) return nullptr;
        }
        const std::string missing = analyzer.validateGotos();
        return Py_BuildValue("{s:O,s:O,s:s,s:O}", "labels", labels.get(), "rows", rows.get(),
            "missing", missing.c_str(), "init", analyzer.hasInitStep() ? Py_True : Py_False);
    } catch (const SPELLcoreException& error) { return failure(error); }
}
struct GotoTrace { PyCodeObject* code; SPELLgoto* analyzer; int count; };
static int trace_goto(PyObject* capsule, PyFrameObject* frame, int event, PyObject*) {
    auto* state = static_cast<GotoTrace*>(PyCapsule_GetPointer(capsule, "SPELL.goto.trace"));
    if (!state) return -1;
    SPELLpython313::Owned code(reinterpret_cast<PyObject*>(PyFrame_GetCode(frame)));
    if (event != PyTrace_LINE || code.get() != reinterpret_cast<PyObject*>(state->code)) return 0;
    int target = state->analyzer->getTargetLine(PyFrame_GetLineNumber(frame));
    if (target < 0) return 0;
    if (++state->count > 64) { PyErr_SetString(PyExc_RuntimeError, "qualification jump limit"); return -1; }
    try { SPELLpythonHelper::instance().setNewLine(frame, target, -1); }
    catch (const SPELLcoreException& error) { failure(error); return -1; }
    return 0;
}
static PyObject* goto_trace(PyObject*, PyObject* args) {
    PyObject *code, *globals;
    if (!PyArg_ParseTuple(args, "OO", &code, &globals)) return nullptr;
    if (!PyCode_Check(code) || !PyDict_Check(globals)) {
        PyErr_SetString(PyExc_TypeError, "expected code and globals dictionary"); return nullptr;
    }
    try {
        SPELLgoto analyzer(reinterpret_cast<PyCodeObject*>(code));
        GotoTrace state{reinterpret_cast<PyCodeObject*>(code), &analyzer, 0};
        SPELLpython313::Owned capsule(PyCapsule_New(&state, "SPELL.goto.trace", nullptr));
        if (!capsule.get()) return nullptr;
        PyEval_SetTrace(trace_goto, capsule.get());
        SPELLpython313::Owned result(PyEval_EvalCode(code, globals, globals));
        PyEval_SetTrace(nullptr, nullptr);
        if (!result.get()) return nullptr;
        return PyLong_FromLong(state.count);
    } catch (const SPELLcoreException& error) { return failure(error); }
}
struct Watch: SPELLvariableChangeListener {
    PyObject* frame;
    std::set<std::string> ignored;
    std::unique_ptr<SPELLvariableMonitor> monitor;
    std::vector<std::array<std::vector<SPELLvarInfo>,3>> changes;
    Watch(PyObject* input, const std::set<std::string>& excluded): frame(Py_NewRef(input)), ignored(excluded) {
        monitor = std::make_unique<SPELLvariableMonitor>(this, reinterpret_cast<PyFrameObject*>(input), ignored);
        SPELLvariableMonitor::s_enabled = true;
    }
    void close() { monitor.reset(); Py_CLEAR(frame); }
    ~Watch() { close(); }
    void variableChanged(const std::vector<SPELLvarInfo>& added, const std::vector<SPELLvarInfo>& changed,
                         const std::vector<SPELLvarInfo>& deleted) override { changes.push_back({added,changed,deleted}); }
};
static Watch* watch(PyObject* capsule) {
    auto* value = static_cast<Watch*>(PyCapsule_GetPointer(capsule, "SPELL.watch"));
    if (value && !value->monitor) { PyErr_SetString(PyExc_RuntimeError, "watch is closed"); return nullptr; }
    return value;
}
static void watch_destroy(PyObject* capsule) { delete static_cast<Watch*>(PyCapsule_GetPointer(capsule, "SPELL.watch")); }
static PyObject* watch_create(PyObject*, PyObject* args) {
    PyObject *frame, *ignored;
    if (!PyArg_ParseTuple(args, "OO", &frame, &ignored)) return nullptr;
    if (!PyFrame_Check(frame)) { PyErr_SetString(PyExc_TypeError, "expected live frame"); return nullptr; }
    SPELLpython313::Owned sequence(PySequence_Fast(ignored, "expected ignored names"));
    if (!sequence.get()) return nullptr;
    std::set<std::string> names;
    for (Py_ssize_t i = 0; i < PySequence_Fast_GET_SIZE(sequence.get()); ++i) {
        const char* name = PyUnicode_AsUTF8(PySequence_Fast_GET_ITEM(sequence.get(), i));
        if (!name) return nullptr;
        names.insert(name);
    }
    std::unique_ptr<Watch> instance(new Watch(frame, names));
    try { instance->monitor->initialize(); }
    catch (const SPELLcoreException& e) { return failure(e); }
    PyObject* capsule = PyCapsule_New(instance.get(), "SPELL.watch", watch_destroy);
    if (capsule) instance.release();
    return capsule;
}
static PyObject* watch_close(PyObject*, PyObject* capsule) {
    auto* instance = static_cast<Watch*>(PyCapsule_GetPointer(capsule, "SPELL.watch"));
    if (!instance) return nullptr;
    instance->close(); Py_RETURN_NONE;
}
static PyObject* info_object(const SPELLvarInfo& info) {
    return Py_BuildValue("{s:s,s:s,s:s,s:O,s:O,s:O}", "name", info.varName.c_str(), "type", info.varType.c_str(),
        "value", info.varValue.c_str(), "global", info.isGlobal ? Py_True : Py_False,
        "added", info.isAdded ? Py_True : Py_False, "deleted", info.isDeleted ? Py_True : Py_False);
}
static PyObject* map_object(const SPELLvariableMonitor::VarMap& map) {
    SPELLpython313::Owned result(PyDict_New());
    if (!result.get()) return nullptr;
    for (const auto& entry: map) {
        SPELLpython313::Owned info(info_object(entry.second));
        if (!info.get() || PyDict_SetItemString(result.get(), entry.first.c_str(), info.get()) < 0) return nullptr;
    }
    return Py_NewRef(result.get());
}
static PyObject* watch_state(PyObject*, PyObject* capsule) {
    auto* instance = watch(capsule); if (!instance) return nullptr;
    try {
        SPELLpython313::Owned globals(map_object(instance->monitor->getGlobalVariables()));
        SPELLpython313::Owned locals(map_object(instance->monitor->getLocalVariables()));
        if (!globals.get() || !locals.get()) return nullptr;
        return Py_BuildValue("{s:O,s:O}", "globals", globals.get(), "locals", locals.get());
    } catch (const SPELLcoreException& e) { return failure(e); }
}
static PyObject* watch_analyze(PyObject*, PyObject* capsule) {
    auto* instance = watch(capsule); if (!instance) return nullptr;
    try { instance->monitor->analyze(); }
    catch (const SPELLcoreException& e) { return failure(e); }
    Py_RETURN_NONE;
}
static PyObject* watch_events(PyObject*, PyObject* capsule) {
    auto* instance = watch(capsule); if (!instance) return nullptr;
    SPELLpython313::Owned result(PyList_New(0));
    if (!result.get()) return nullptr;
    for (const auto& event: instance->changes) {
        SPELLpython313::Owned row(PyList_New(0));
        if (!row.get()) return nullptr;
        for (const auto& values: event) {
            SPELLpython313::Owned group(PyList_New(0));
            if (!group.get()) return nullptr;
            for (const auto& value: values) {
                SPELLpython313::Owned info(info_object(value));
                if (!info.get() || PyList_Append(group.get(), info.get()) < 0) return nullptr;
            }
            if (PyList_Append(row.get(), group.get()) < 0) return nullptr;
        }
        if (PyList_Append(result.get(), row.get()) < 0) return nullptr;
    }
    instance->changes.clear();
    return Py_NewRef(result.get());
}
static PyObject* watch_change(PyObject*, PyObject* args) {
    PyObject* capsule;
    const char *name, *expression;
    int global;
    if (!PyArg_ParseTuple(args, "Ossp", &capsule, &name, &expression, &global)) return nullptr;
    auto* instance = watch(capsule); if (!instance) return nullptr;
    SPELLvarInfo info(name, "", expression, global);
    try { instance->monitor->changeVariable(info); }
    catch (const SPELLcoreException& e) { return failure(e); }
    return info_object(info);
}
static PyObject* watch_get(PyObject*, PyObject* args) {
    PyObject* capsule; const char* name;
    if (!PyArg_ParseTuple(args, "Os", &capsule, &name)) return nullptr;
    auto* instance = watch(capsule); if (!instance) return nullptr;
    SPELLvarInfo info(name, "", "", false);
    try { instance->monitor->getVariable(info); }
    catch (const SPELLcoreException& e) { return failure(e); }
    return info_object(info);
}
static PyObject* watch_ref(PyObject*, PyObject* args) {
    PyObject* capsule; const char* name;
    if (!PyArg_ParseTuple(args, "Os", &capsule, &name)) return nullptr;
    auto* instance = watch(capsule); if (!instance) return nullptr;
    try {
        PyObject* value = instance->monitor->getVariableRef(name);
        return Py_NewRef(value ? value : Py_None);
    } catch (const SPELLcoreException& e) { return failure(e); }
}
static PyObject* analysis_compile(PyObject*, PyObject* source) {
    Py_ssize_t size;
    const char* value = PyUnicode_AsUTF8AndSize(source, &size);
    if (!value) return nullptr;
    try { return reinterpret_cast<PyObject*>(SPELLpythonHelper::instance().compileScript(std::string(value, size))); }
    catch (const SPELLcoreException& e) { return failure(e); }
}
static PyObject* bytecode_info(PyObject*, PyObject* args) {
    PyObject* code;
    int count;
    if (!PyArg_ParseTuple(args, "Oi", &code, &count)) return nullptr;
    if (!PyCode_Check(code) || count < 0 || count > 10000) {
        PyErr_SetString(PyExc_ValueError, "expected code and 0..10000 lines"); return nullptr;
    }
    try {
        SPELLbytecode analyzer(reinterpret_cast<PyCodeObject*>(code));
        SPELLpython313::Owned rows(PyList_New(0));
        if (!rows.get()) return nullptr;
        for (int n = 1; n <= count; ++n) {
            SPELLpython313::Owned row(Py_BuildValue("(iiiiiiiii)", n, analyzer.isExecutable(n),
                analyzer.isKeepWithNext(n), analyzer.isReturnConstant(n), analyzer.isInTryBlock(n),
                analyzer.isInExceptBlock(n), analyzer.isInFinallyBlock(n), analyzer.isTryBlockEnd(n),
                analyzer.tryBlockEndLine(n)));
            if (!row.get() || PyList_Append(rows.get(), row.get()) < 0) return nullptr;
        }
        return Py_BuildValue("{s:O,s:i,s:i}", "rows", rows.get(), "last_address", analyzer.getLastAddress(),
                            "last_line", analyzer.getLastLine());
    } catch (const SPELLcoreException& e) { return failure(e); }
}
#include "qualify_manager.inc"
#include "qualify_ws.inc"
static PyMethodDef methods[] = {
    {"ws_frame_create",ws_frame_create,METH_VARARGS,nullptr},
    {"ws_frame_event",ws_frame_event,METH_VARARGS,nullptr},
    {"ws_frame_state",ws_frame_state,METH_O,nullptr},
    {"ws_frame_view",ws_frame_view,METH_O,nullptr},
    {"ws_frame_resume",ws_frame_resume,METH_O,nullptr},
    {"ws_frame_set",ws_frame_set,METH_VARARGS,nullptr},
    {"ws_frame_rebind",ws_frame_rebind,METH_VARARGS,nullptr},
    {"manager_create", manager_create, METH_O, nullptr}, {"manager_close", manager_close, METH_O, nullptr},
    {"manager_script", manager_script, METH_VARARGS, nullptr}, {"manager_event", manager_event, METH_VARARGS, nullptr},
    {"manager_copy", manager_copy, METH_VARARGS, nullptr}, {"manager_definitions", manager_definitions, METH_O, nullptr},
    {"manager_initialize", manager_initialize, METH_VARARGS, nullptr}, {"manager_execute", manager_execute, METH_VARARGS, nullptr},
    {"manager_stop", manager_stop, METH_O, nullptr},
    {"ws_filter_set", ws_filter_set, METH_O, nullptr}, {"ws_filter_test", ws_filter_test, METH_VARARGS, nullptr},
    {"create", create, METH_NOARGS, nullptr},
    {"process", process, METH_VARARGS, nullptr},
    {"classify", classify, METH_VARARGS, nullptr},
    {"lines", lines, METH_O, nullptr},
    {"goto_info", goto_info, METH_VARARGS, nullptr},
    {"goto_trace", goto_trace, METH_VARARGS, nullptr},
    {"watch_create", watch_create, METH_VARARGS, nullptr}, {"watch_close", watch_close, METH_O, nullptr},
    {"watch_state", watch_state, METH_O, nullptr}, {"watch_analyze", watch_analyze, METH_O, nullptr},
    {"watch_events", watch_events, METH_O, nullptr}, {"watch_change", watch_change, METH_VARARGS, nullptr},
    {"watch_get", watch_get, METH_VARARGS, nullptr}, {"watch_ref", watch_ref, METH_VARARGS, nullptr},
    {"compile_source", analysis_compile, METH_O, nullptr}, {"bytecode_info", bytecode_info, METH_VARARGS, nullptr},
    {nullptr, nullptr, 0, nullptr}
};
static PyModuleDef module = {PyModuleDef_HEAD_INIT, "_spell_analysis_qualification", nullptr, -1, methods};
PyMODINIT_FUNC PyInit__spell_analysis_qualification() { return PyModule_Create(&module); }
