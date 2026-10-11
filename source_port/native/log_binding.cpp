// SPDX-License-Identifier: GPL-3.0-or-later
static PyObject* Log_Call(PyObject*, PyObject* args, PyObject* kwargs)
{
    const char* message=nullptr;
    const char* severity=LOG_SEVERITY_STR[LOG_INFO].c_str();
    const char* level=LOG_LEVEL_STR[LOG_PROC].c_str();
    static const char* names[]={"message","severity","level",nullptr};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"s|ss:LOG",const_cast<char**>(names),&message,&severity,&level))
        return nullptr;
    auto sev=str_to_sev.find(severity);
    if (sev==str_to_sev.end() || str_to_lev.find(level)==str_to_lev.end()) {
        PyErr_SetString(PyExc_ValueError,"Unknown SPELL log severity or level");
        return nullptr;
    }
    try {
        switch (sev->second) {
            case LOG_INFO: LOG_INFO_PY(message); break;
            case LOG_WARN: LOG_WARN_PY(message); break;
            case LOG_ERROR: LOG_ERROR_PY(message); break;
            default: break;
        }
    } catch (const std::exception& error) {
        PyErr_SetString(PyExc_RuntimeError,error.what()); return nullptr;
    } catch (...) {
        PyErr_SetString(PyExc_RuntimeError,"SPELL logger failed"); return nullptr;
    }
    Py_RETURN_NONE;
}

static PyObject* Log_Reduce(PyObject*,PyObject*) { return PyUnicode_FromString("LOG"); }

void Log_Install()
{
    static PyMethodDef methods[]={
        {"__reduce__",Log_Reduce,METH_NOARGS,"Reference the current runtime logger"},
        {nullptr,nullptr,0,nullptr}};
    static PyType_Slot slots[]={
        {Py_tp_new,reinterpret_cast<void*>(PyType_GenericNew)},
        {Py_tp_call,reinterpret_cast<void*>(Log_Call)},
        {Py_tp_methods,reinterpret_cast<void*>(methods)},
        {0,nullptr}};
    static PyType_Spec spec={"spell.utils.log.NativeLog",sizeof(PyLogObject),0,
        Py_TPFLAGS_DEFAULT | Py_TPFLAGS_IMMUTABLETYPE,slots};
    SPELLpython313::Owned type(PyType_FromSpec(&spec));
    if (!type.get()) SPELLpythonHelper::instance().checkError();
    SPELLpython313::Owned log(PyObject_CallNoArgs(type.get()));
    if (!log.get()) SPELLpythonHelper::instance().checkError();
    SPELLpythonHelper::instance().install(log.get(),"LOG","spell.utils.log");
    for (int count=0; count<LOG_LEV_MAX; ++count) {
        SPELLpython313::Owned value(SSTRPY(LOG_LEVEL_STR[count]));
        if (!value.get()) SPELLpythonHelper::instance().checkError();
        SPELLpythonHelper::instance().install(value.get(),LOG_LEVEL_LBL[count],"spell.utils.log");
        str_to_lev.insert(std::make_pair(LOG_LEVEL_STR[count],static_cast<LogLevel>(count)));
    }
    for (int count=0; count<LOG_SEV_MAX; ++count) {
        SPELLpython313::Owned value(SSTRPY(LOG_SEVERITY_STR[count]));
        if (!value.get()) SPELLpythonHelper::instance().checkError();
        SPELLpythonHelper::instance().install(value.get(),LOG_SEVERITY_LBL[count],"spell.utils.log");
        str_to_sev.insert(std::make_pair(LOG_SEVERITY_STR[count],static_cast<LogSeverity>(count)));
    }
}
