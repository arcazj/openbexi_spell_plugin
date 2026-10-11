// SPDX-License-Identifier: GPL-3.0-or-later
// Replacement compiler/line setter bodies in upstream SPELLpythonHelper.C.
PyCodeObject* SPELLpythonHelper::compile(const std::string& filePath)
{
    std::string source = readProcedureFile(filePath);
    if (source.empty())
        THROW_EXCEPTION("Unable to compile script", "Cannot read source code", SPELL_ERROR_PYTHON_API);
    if (source.find('\0') != std::string::npos) {
        PyErr_SetString(PyExc_SyntaxError, "source code cannot contain null bytes");
        checkError();
    }
    PyCompilerFlags flags = {};
    PyObject* code = Py_CompileStringExFlags(source.c_str(), filePath.c_str(),
                                            Py_file_input, &flags, -1);
    if (!code) checkError();
    return reinterpret_cast<PyCodeObject*>(code);
}

PyCodeObject* SPELLpythonHelper::compileScript(const std::string& source)
{
    // Reject embedded NUL explicitly: the C compiler API takes a C string.
    if (source.find('\0') != std::string::npos) {
        PyErr_SetString(PyExc_SyntaxError, "source code cannot contain null bytes");
        checkError();
    }
    PyCompilerFlags flags = {};
    PyObject* code = Py_CompileStringExFlags(source.c_str(), "<string>",
                                            Py_file_input, &flags, -1);
    if (!code) checkError();
    return reinterpret_cast<PyCodeObject*>(code);
}

bool SPELLpythonHelper::setNewLine(PyFrameObject* frame, const int& new_lineno,
                                  const int& new_lasti)
{
    // CPython owns bytecode offsets and exception-stack validation. A jump is
    // legal only in its supported trace events; never mutate internal stacks.
    (void)new_lasti;
    SPELLpython313::Owned line(PyLong_FromLong(new_lineno));
    if (!line.get() || PyObject_SetAttrString(reinterpret_cast<PyObject*>(frame),
                                             "f_lineno", line.get()) < 0)
        checkError();
    return true;
}
