// SPDX-License-Identifier: GPL-3.0-or-later
SPELLcoreException* SPELLerror::errorToException()
{
    SPELLpython313::Owned value(PyErr_GetRaisedException());
    if (!value.get()) return nullptr;
    // Control state, not a user-supplied message alone, identifies a stop.
    if (Py_TYPE(value.get()) == reinterpret_cast<PyTypeObject*>(PyExc_RuntimeError)) {
        std::string reason = SPELLpython313::text(value.get());
        if ((isExecutionAborted() && reason == "EXECUTION ABORTED") ||
            (isExecutionTerminated() && reason == "EXECUTION TERMINATED")) return nullptr;
    }
    SPELLpython313::Owned traceback(PyException_GetTraceback(value.get()));
    PyObject* type = reinterpret_cast<PyObject*>(Py_TYPE(value.get()));
    return errorToException(type, type, value.get(), traceback.get());
}

SPELLcoreException* SPELLerror::errorToException(PyObject* err, PyObject* ptype,
                                               PyObject* pvalue, PyObject* ptraceback)
{
    // All arguments are borrowed; the caller owns the normalized exception.
    std::string reason = SPELLpython313::text(pvalue);
    std::string message = "Python error";
    SPELLerrorCode code = SPELL_PYERROR_OTHER;
    struct Kind { PyObject* type; SPELLerrorCode code; const char* label; };
    Kind kinds[] = {
        {PyExc_ImportError, SPELL_PYERROR_IMPORT, "Import error"},
        {PyExc_IndexError, SPELL_PYERROR_INDEX, "Index error"},
        {PyExc_KeyError, SPELL_PYERROR_KEY, "Key error"},
        {PyExc_MemoryError, SPELL_PYERROR_MEMORY, "Memory error"},
        {PyExc_NameError, SPELL_PYERROR_NAME, "Name error"},
        {PyExc_SyntaxError, SPELL_PYERROR_SYNTAX, "Syntax error"},
        {PyExc_TypeError, SPELL_PYERROR_TYPE, "Type error"},
        {PyExc_ValueError, SPELL_PYERROR_VALUE, "Value error"}
    };
    for (const auto& kind: kinds) {
        if (PyErr_GivenExceptionMatches(ptype ? ptype : err, kind.type)) {
            code = kind.code; message = kind.label; break;
        }
    }
    PyObject* modules = PyImport_GetModuleDict();
    PyObject* module = PyDict_GetItemString(modules, "spell.lib.exception");
    PyObject* spellClass = module && PyModule_Check(module)
        ? PyDict_GetItemString(PyModule_GetDict(module), "SpellException") : nullptr;
    if (spellClass && PyType_Check(spellClass) &&
        PyErr_GivenExceptionMatches(ptype ? ptype : err, spellClass)) {
        code = SPELL_DRIVER_ERROR;
        SPELLpython313::Owned msg(PyObject_GetAttrString(pvalue, "message"));
        if (!msg.get()) PyErr_Clear();
        SPELLpython313::Owned why(PyObject_GetAttrString(pvalue, "reason"));
        if (!why.get()) PyErr_Clear();
        message = "Driver error: " + (msg.get() ? SPELLpython313::text(msg.get()) : reason);
        if (why.get()) reason = SPELLpython313::text(why.get());
    }
    if (ptraceback && PyTraceBack_Check(ptraceback)) {
        for (auto* tb = reinterpret_cast<PyTracebackObject*>(ptraceback); tb; tb = tb->tb_next)
            message += "\n - file '" + SPELLpython313::filename(tb->tb_frame)
                + "', line " + std::to_string(tb->tb_lineno);
    }
    return new SPELLcoreException(message, reason, code, false);
}
