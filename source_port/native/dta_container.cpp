// SPDX-License-Identifier: GPL-3.0-or-later
// CPython ownership port of the original SPELLdtaContainer implementation.
#include "SPELL_DTA/SPELLdtaContainer.H"
#include "SPELL_DTA/SPELLdtaVariableObject.H"
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_UTIL/SPELLpythonMonitors.H"
#include "SPELL_WRP/SPELLconstants.H"
namespace {
using SPELLpython313::Owned;
struct VarClass {
    Owned module, type;
    VarClass(): module(PyImport_ImportModule(MOD_NAME(libSPELL_DTA))),
        type(module.get() ? PyObject_GetAttrString(module.get(), "Var") : nullptr) {
        if (!module.get() || !type.get()) SPELLpythonHelper::instance().checkError();
        if (!PyType_Check(type.get())) {
            PyErr_SetString(PyExc_TypeError, "SPELL Var type is unavailable");
            SPELLpythonHelper::instance().checkError();
        }
    }
    bool matches(PyObject* value) { return PyObject_TypeCheck(value, reinterpret_cast<PyTypeObject*>(type.get())); }
};
SPELLdtaVariable* var(PyObject* object) {
    auto* value = reinterpret_cast<SPELLdtaVariableObject*>(object)->var;
    if (!value) THROW_EXCEPTION("Cannot use variable", "Uninitialized native Var", SPELL_ERROR_LANGUAGE);
    return value;
}
}
bool SPELLdtaContainer::s_notificationsEnabled = true;
SPELLdtaContainer::SPELLdtaContainer(const std::string& name): m_name(name), m_dict(PyDict_New()), m_notificationsEnabled(true) {
    if (!m_dict) SPELLpythonHelper::instance().checkError();
}
SPELLdtaContainer::~SPELLdtaContainer() { clear(false); Py_XDECREF(m_dict); }
void SPELLdtaContainer::clear(bool releaseValues) {
    if (!m_dict) return;
    Py_ssize_t index = 0;
    PyObject *key, *value;
    while (PyDict_Next(m_dict, &index, &key, &value)) {
        // The dictionary is private and contains only checked native Vars.
        auto* variable = reinterpret_cast<SPELLdtaVariableObject*>(value)->var;
        if (variable) variable->detachContainer(this);
    }
    if (releaseValues) PyDict_Clear(m_dict);
}
void SPELLdtaContainer::setValue(PyObject* key, PyObject* value) {
    SPELLsafePythonOperations operations("DTA");
    VarClass type;
    Owned previous(Py_XNewRef(PyDict_GetItemWithError(m_dict, key)));
    if (PyErr_Occurred()) SPELLpythonHelper::instance().checkError();
    if (type.matches(value)) {
        auto* variable = var(value);
        if (PyDict_SetItem(m_dict, key, value)<0) SPELLpythonHelper::instance().checkError();
        if (previous.get() && previous.get() != value) var(previous.get())->detachContainer(this);
        variable->setContainer(this);
        variable->setName(SPELLpython313::text(key));
    } else if (previous.get()) {
        auto* variable = var(previous.get());
        try { variable->setValue(value); }
        catch (const SPELLcoreException& error) {
            std::string message = error.what();
            while (!variable->promptForValue(message)) {}
        }
    } else {
        Owned args(PyTuple_New(0)), keywords(PyDict_New());
        if (!args.get() || !keywords.get() || PyDict_SetItemString(keywords.get(), LanguageModifiers::Default.c_str(), value)<0)
            SPELLpythonHelper::instance().checkError();
        Owned instance(PyObject_Call(type.type.get(), args.get(), keywords.get()));
        if (!instance.get()) SPELLpythonHelper::instance().checkError();
        if (PyDict_SetItem(m_dict, key, instance.get())<0) SPELLpythonHelper::instance().checkError();
        auto* variable = var(instance.get());
        variable->setContainer(this);
        variable->setName(SPELLpython313::text(key));
    }
}
PyObject* SPELLdtaContainer::getValueEx(PyObject* key) {
    PyObject* result = PyDict_GetItemWithError(m_dict, key); // original borrowed-reference contract
    if (!result && PyErr_Occurred()) SPELLpythonHelper::instance().checkError();
    return result;
}
PyObject* SPELLdtaContainer::getValue(PyObject* key) {
    SPELLsafePythonOperations operations("DTA");
    Owned object(Py_XNewRef(getValueEx(key)));
    if (!object.get()) {
        VarClass type;
        object.reset(PyObject_CallNoArgs(type.type.get()));
        if (!object.get()) SPELLpythonHelper::instance().checkError();
        if (PyDict_SetItem(m_dict, key, object.get())<0) SPELLpythonHelper::instance().checkError();
        auto* variable = var(object.get());
        variable->setContainer(this);
        variable->setName(SPELLpython313::text(key));
        std::string message = "Data set '" + m_name + "' does not contain variable '" + SPELLpython313::text(key) + "'.\nPlease provide a value for it.";
        while (!variable->promptForValue(message)) {}
        return variable->getValue();
    }
    auto* variable = var(object.get());
    try {
        Owned result(variable->getValue());
        if (variable->getConfirmGet()) return variable->confirmValue();
        return Py_XNewRef(result.get());
    } catch (const SPELLcoreException&) {
        std::string message = "Variable '" + SPELLpython313::text(key) + "' in set '" + m_name + "' is not initialized, please provide a value.";
        while (!variable->promptForValue(message)) {}
        return variable->getValue();
    }
}
bool SPELLdtaContainer::hasKey(PyObject* key) {
    int result = PyDict_Contains(m_dict, key);
    if (result < 0) SPELLpythonHelper::instance().checkError();
    return result != 0;
}
PyObject* SPELLdtaContainer::getKeys() { return PyDict_Keys(m_dict); }
