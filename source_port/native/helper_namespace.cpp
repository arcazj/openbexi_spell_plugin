// SPDX-License-Identifier: GPL-3.0-or-later
PyObject* SPELLpythonHelper::getMainDict()
{
    // Interpreter-local SPELL services and exports. Ordinary Python builtins
    // remain untouched; procedure globals are supplied by the frame manager.
    PyObject* module = PyImport_AddModule("spell.runtime"); // borrowed
    if (!module) checkError();
    PyObject* dict = PyModule_GetDict(module);
    if (!PyDict_GetItemString(dict,"__builtins__") &&
        PyDict_SetItemString(dict,"__builtins__",PyEval_GetBuiltins())<0) checkError();
    return dict;
}

void SPELLpythonHelper::install(PyObject* object, const std::string& name)
{
    if (!object) { PyErr_SetString(PyExc_ValueError,"Cannot install a null SPELL export"); checkError(); }
    if (PyDict_SetItemString(getMainDict(),name.c_str(),object)<0) checkError();
}

void SPELLpythonHelper::install(PyObject* object, const std::string& name, const std::string& module)
{
    SPELLpython313::Owned owner(PyImport_ImportModule(module.c_str()));
    if (!owner.get() || PyObject_SetAttrString(owner.get(),name.c_str(),object)<0) checkError();
}

void SPELLpythonHelper::importAllFrom(const std::string& package)
{
    SPELLpython313::Owned module(PyImport_ImportModule(package.c_str()));
    if (!module.get()) checkError();
    PyObject* exports = nullptr;
    if (PyObject_GetOptionalAttrString(module.get(),"__all__",&exports)<0) checkError();
    SPELLpython313::Owned names(exports ? exports : PyObject_Dir(module.get()));
    SPELLpython313::Owned sequence(PySequence_Fast(names.get(),"Expected module export names"));
    if (!sequence.get()) checkError();
    for (Py_ssize_t i=0; i<PySequence_Fast_GET_SIZE(sequence.get()); ++i) {
        PyObject* name=PySequence_Fast_GET_ITEM(sequence.get(),i);
        if (!PyUnicode_Check(name)) { PyErr_SetString(PyExc_TypeError,"Export names must be strings"); checkError(); }
        const char* label=PyUnicode_AsUTF8(name);
        if (!label) checkError();
        if (!exports && label[0]=='_') continue;
        SPELLpython313::Owned value(PyObject_GetAttr(module.get(),name));
        if (!value.get() || PyDict_SetItem(getMainDict(),name,value.get())<0) checkError();
    }
}

void SPELLpythonHelper::updateBuiltinsWith(const std::string& package)
{
    // Retain the C++ entry point for upstream callers, with isolated exports.
    importAllFrom(package);
}
