// SPDX-License-Identifier: GPL-3.0-or-later
PyFrameObject* SPELLpythonHelper::createFrame(const std::string& filename, PyCodeObject* code, PyObject* globals)
{
    SPELLpython313::GIL gil;
    if (!code || !PyCode_Check(reinterpret_cast<PyObject*>(code))) {
        PyErr_SetString(PyExc_TypeError, "Expected procedure code");
        checkError();
    }
    if (!globals) {
        PyObject* module = PyImport_AddModule("__main__"); // borrowed
        if (!module) checkError();
        globals = PyModule_GetDict(module); // borrowed
        if (!globals) checkError();
    }
    if (!PyDict_Check(globals)) { PyErr_SetString(PyExc_TypeError,"Expected procedure namespace dictionary"); checkError(); }
    if (!PyDict_GetItemString(globals,"__builtins__")
        && PyDict_SetItemString(globals,"__builtins__",PyEval_GetBuiltins())<0) checkError();
    SPELLpython313::Owned file(PyUnicode_DecodeFSDefaultAndSize(filename.data(), filename.size()));
    if (!file.get() || PyDict_SetItemString(globals, "__file__", file.get())<0) checkError();
    // Module execution uses one namespace for locals and globals, so functions
    // declared by a procedure can resolve its other top-level definitions.
    PyFrameObject* frame = PyFrame_New(PyThreadState_Get(), code, globals, globals);
    if (!frame) checkError();
    return frame; // Exactly one owned reference.
}

PyFrameObject* SPELLpythonHelper::createFrameFromFunction(const std::string&, PyObject* function)
{
    SPELLpython313::GIL gil;
    if (!function || !PyFunction_Check(function)) {
        PyErr_SetString(PyExc_TypeError, "Expected a Python function");
        checkError();
    }
    auto* code = reinterpret_cast<PyCodeObject*>(PyFunction_GetCode(function)); // borrowed
    PyObject* globals = PyFunction_GetGlobals(function); // borrowed
    PyFrameObject* frame = PyFrame_New(PyThreadState_Get(), code, globals, nullptr);
    if (!frame) checkError();
    return frame; // PyFrame_New owns its references to code and globals.
}

//=============================================================================
