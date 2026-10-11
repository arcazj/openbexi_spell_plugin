// SPDX-License-Identifier: GPL-3.0-or-later
// Qualification adapter for the actual original analyzer classes.
#include "SPELL_EXC/SPELLastAnalyzer.H"
#include "SPELL_EXC/SPELLlnotab.H"
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
static PyMethodDef methods[] = {
    {"create", create, METH_NOARGS, nullptr},
    {"process", process, METH_VARARGS, nullptr},
    {"classify", classify, METH_VARARGS, nullptr},
    {"lines", lines, METH_O, nullptr},
    {nullptr, nullptr, 0, nullptr}
};
static PyModuleDef module = {PyModuleDef_HEAD_INIT, "_spell_analysis_qualification", nullptr, -1, methods};
PyMODINIT_FUNC PyInit__spell_analysis_qualification() { return PyModule_Create(&module); }
