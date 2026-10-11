// SPDX-License-Identifier: GPL-3.0-or-later
// Qualification adapter for the actual original analyzer classes.
#include "SPELL_EXC/SPELLastAnalyzer.H"
#include "SPELL_EXC/SPELLlnotab.H"
#include "SPELL_EXC/SPELLgoto.H"
#include "SPELL_UTIL/SPELLpython313.H"

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
static PyMethodDef methods[] = {
    {"create", create, METH_NOARGS, nullptr},
    {"process", process, METH_VARARGS, nullptr},
    {"classify", classify, METH_VARARGS, nullptr},
    {"lines", lines, METH_O, nullptr},
    {"goto_info", goto_info, METH_VARARGS, nullptr},
    {"goto_trace", goto_trace, METH_VARARGS, nullptr},
    {nullptr, nullptr, 0, nullptr}
};
static PyModuleDef module = {PyModuleDef_HEAD_INIT, "_spell_analysis_qualification", nullptr, -1, methods};
PyMODINIT_FUNC PyInit__spell_analysis_qualification() { return PyModule_Create(&module); }
