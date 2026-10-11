// SPDX-License-Identifier: GPL-3.0-or-later
PyFrameObject* SPELLpythonHelper::createFrame(const std::string& filename, PyCodeObject* code)
{
    SPELLpython313::GIL gil;
    if (!code || !PyCode_Check(reinterpret_cast<PyObject*>(code))) {
        PyErr_SetString(PyExc_TypeError, "Expected procedure code");
        checkError();
    }
    PyObject* module = PyImport_AddModule("__main__"); // borrowed
    if (!module) checkError();
    PyObject* globals = PyModule_GetDict(module); // borrowed
    if (!globals) checkError();
    SPELLpython313::Owned file(PyUnicode_DecodeFSDefaultAndSize(filename.data(), filename.size()));
    if (!file.get() || PyDict_SetItemString(globals, "__file__", file.get())<0) checkError();
    PyFrameObject* frame = PyFrame_New(PyThreadState_Get(), code, globals, nullptr);
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
