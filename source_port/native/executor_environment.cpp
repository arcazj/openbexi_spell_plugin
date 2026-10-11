// SPDX-License-Identifier: GPL-3.0-or-later
void SPELLexecutorImpl::installCallingArguments()
{
    using SPELLpython313::Owned;
    auto& helper=SPELLpythonHelper::instance();
    const std::string& expression=getConfiguration().getArguments();
    Owned values(expression.empty() ? PyDict_New() : helper.eval(expression,false));
    if (!values.get()) helper.checkError();
    if (!PyDict_Check(values.get())) {
        PyErr_SetString(PyExc_TypeError,"Procedure arguments must evaluate to a dictionary");
        helper.checkError();
    }
    PyObject* type=helper.getObject(MOD_NAME(libSPELL_DTA),"DataContainer"); // module-owned
    Owned name(PyUnicode_FromString("Calling Arguments"));
    Owned args(PyObject_CallOneArg(type,name.get()));
    if (!args.get()) helper.checkError();
    struct Notifications {
        bool previous=SPELLdtaContainer::areGlobalnotificationsEnabled();
        Notifications() { SPELLdtaContainer::setGlobalNotificationsEnabled(false); }
        ~Notifications() { SPELLdtaContainer::setGlobalNotificationsEnabled(previous); }
    } notifications;
    Py_ssize_t position=0;
    PyObject *key=nullptr,*value=nullptr;
    while (PyDict_Next(values.get(),&position,&key,&value)) {
        Owned result(PyObject_CallMethod(args.get(),"set","OO",key,value));
        if (!result.get()) helper.checkError();
    }
    helper.install(args.get(),"ARGS");
}

void SPELLexecutorImpl::installInternalVariables()
{
    auto& helper=SPELLpythonHelper::instance();
    PyObject* type=helper.getObject(MOD_NAME(libSPELL_DTA),"DataContainer");
    SPELLpython313::Owned name(PyUnicode_FromString("Internal Variables"));
    SPELLpython313::Owned variables(PyObject_CallOneArg(type,name.get()));
    if (!variables.get()) helper.checkError();
    helper.install(variables.get(),"IVARS");
}
