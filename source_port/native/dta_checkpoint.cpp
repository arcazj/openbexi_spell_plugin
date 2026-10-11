// SPDX-License-Identifier: GPL-3.0-or-later
// Private pickle protocol for the original native DTA types; no CIF side effects.
#include "SPELL_UTIL/SPELLpython313.H"
#include <memory>
namespace {
using SPELLpython313::Owned;
PyObject* checkpointError(const SPELLcoreException& error) {
    PyErr_SetString(PyExc_ValueError,(error.getError()+": "+error.getReason()).c_str()); return nullptr;
}
struct SilentDataRestore {
    bool previous=SPELLdtaContainer::areGlobalnotificationsEnabled();
    SilentDataRestore() { SPELLdtaContainer::setGlobalNotificationsEnabled(false); }
    ~SilentDataRestore() { SPELLdtaContainer::setGlobalNotificationsEnabled(previous); }
};
PyObject* nativeType(const char* name) {
    Owned module(PyImport_ImportModule(MOD_NAME(libSPELL_DTA)));
    return module.get() ? PyObject_GetAttrString(module.get(),name) : nullptr;
}
bool nativeInstance(PyObject* object,const char* name) {
    Owned type(nativeType(name));
    if (!type.get()) return false;
    if (!PyType_Check(type.get()) || !PyObject_TypeCheck(object,reinterpret_cast<PyTypeObject*>(type.get()))) {
        PyErr_SetString(PyExc_TypeError,"Invalid native checkpoint type"); return false;
    }
    return true;
}
PyObject* stateString(const std::string& value) { return PyUnicode_FromStringAndSize(value.data(),value.size()); }
bool textState(PyObject* value,std::string& result) {
    Py_ssize_t length=0; const char* text=PyUnicode_AsUTF8AndSize(value,&length);
    if (!text) return false;
    result.assign(text,length); return true;
}
PyObject* pythonState(PyObject* self) {
    Owned getter(PyObject_GetAttrString(reinterpret_cast<PyObject*>(&PyBaseObject_Type),"__getstate__"));
    return getter.get() ? PyObject_CallOneArg(getter.get(),self) : nullptr;
}
bool checkPythonState(PyObject* state) {
    if (state==Py_None || PyDict_Check(state)) return true;
    if (PyTuple_Check(state) && PyTuple_GET_SIZE(state)==2
            && (PyTuple_GET_ITEM(state,0)==Py_None || PyDict_Check(PyTuple_GET_ITEM(state,0)))
            && PyDict_Check(PyTuple_GET_ITEM(state,1))) return true;
    PyErr_SetString(PyExc_ValueError,"Invalid Python subclass state"); return false;
}
bool applyPythonState(PyObject* self,PyObject* state) {
    if (state==Py_None) return true;
    PyObject *attributes=state,*slots=nullptr;
    if (PyTuple_Check(state)) { attributes=PyTuple_GET_ITEM(state,0); slots=PyTuple_GET_ITEM(state,1); }
    if (attributes!=Py_None && PyObject_GenericSetDict(self,attributes,nullptr)<0) return false;
    if (slots) {
        Py_ssize_t position=0; PyObject *key,*value;
        while (PyDict_Next(slots,&position,&key,&value))
            if (PyObject_GenericSetAttr(self,key,value)<0) return false;
    }
    return true;
}
PyObject* valueList(const std::vector<SPELLpyValue>& values) {
    Owned result(PyList_New(values.size())); if (!result.get()) return nullptr;
    for (size_t index=0;index<values.size();++index) {
        PyObject* value=values[index].get(); if (!value) return nullptr;
        PyList_SET_ITEM(result.get(),index,value);
    }
    return Py_NewRef(result.get());
}
PyObject* reduceNative(PyObject* self,const char* factory,PyObject* state) {
    Owned module(PyImport_ImportModule(MOD_NAME(libSPELL_DTA)));
    Owned constructor(module.get() ? PyObject_GetAttrString(module.get(),factory) : nullptr);
    if (!constructor.get()) return nullptr;
    return Py_BuildValue("(O(O)O)",constructor.get(),reinterpret_cast<PyObject*>(Py_TYPE(self)),state);
}
PyObject* variableReduce(PyObject* self,PyObject* protocol) {
    if (!PyLong_Check(protocol)) { PyErr_SetString(PyExc_TypeError,"Expected pickle protocol number"); return nullptr; }
    auto* variable=reinterpret_cast<SPELLdtaVariableObject*>(self)->var;
    if (!variable) { PyErr_SetString(PyExc_RuntimeError,"Uninitialized Var"); return nullptr; }
    try {
        Owned options(PyDict_New()), value(variable->getValueEx()), name(stateString(variable->getName()));
        Owned attributes(pythonState(self));
        if (!options.get() || !value.get() || !name.get() || !attributes.get()) return nullptr;
        if (PyDict_SetItemString(options.get(),"Default",value.get())<0
            || PyDict_SetItemString(options.get(),"Confirm",variable->getConfirmGet() ? Py_True : Py_False)<0) return nullptr;
        for (auto field: {std::make_pair("Type",variable->getType()),std::make_pair("ValueFormat",variable->getFormat())}) {
            if (field.second.empty()) continue;
            // The original constructor infers LIST/DICT from Default but does
            // not accept these internal names as explicit Type modifiers.
            if (std::string(field.first)=="Type" && (field.second=="LIST" || field.second=="DICT")) continue;
            Owned text(stateString(field.second));
            if (!text.get() || PyDict_SetItemString(options.get(),field.first,text.get())<0) return nullptr;
        }
        for (auto field: {std::make_pair("Range",variable->getRange()),std::make_pair("Expected",variable->getExpected())}) {
            if (field.second.empty()) continue;
            Owned values(valueList(field.second));
            if (!values.get() || PyDict_SetItemString(options.get(),field.first,values.get())<0) return nullptr;
        }
        auto* parent=variable->getContainer();
        PyObject* owner=parent ? parent->getOwner() : nullptr;
        Owned state(Py_BuildValue("(iOOOO)",1,name.get(),options.get(),owner ? owner : Py_None,attributes.get()));
        return state.get() ? reduceNative(self,"_checkpoint_new_var",state.get()) : nullptr;
    } catch (const SPELLcoreException& error) { return checkpointError(error); }
}
PyObject* variableSetState(PyObject* self,PyObject* state) {
    int version; PyObject *name,*options,*parent,*attributes;
    if (!PyTuple_Check(state) || !PyArg_ParseTuple(state,"iOOOO",&version,&name,&options,&parent,&attributes)) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError,"Invalid variable checkpoint state"); return nullptr;
    }
    std::string text;
    if (version!=1 || !PyDict_Check(options)) { PyErr_SetString(PyExc_ValueError,"Invalid variable checkpoint version or options"); return nullptr; }
    if (!textState(name,text) || !checkPythonState(attributes)) return nullptr;
    SPELLdtaContainer* container=nullptr;
    if (parent!=Py_None) {
        if (!nativeInstance(parent,"DataContainer")) return nullptr;
        container=reinterpret_cast<SPELLdtaContainerObject*>(parent)->container;
        if (!container) { PyErr_SetString(PyExc_ValueError,"Uninitialized checkpoint parent"); return nullptr; }
    }
    try {
        SilentDataRestore silent;
        auto fresh=std::make_unique<SPELLdtaVariable>(options);
        fresh->setName(text); fresh->setContainer(container);
        if (!applyPythonState(self,attributes)) return nullptr;
        auto* object=reinterpret_cast<SPELLdtaVariableObject*>(self);
        auto* previous=object->var; object->var=fresh.release(); delete previous;
    } catch (const SPELLcoreException& error) { return checkpointError(error); }
    Py_RETURN_NONE;
}
PyObject* containerReduce(PyObject* self,PyObject* protocol) {
    if (!PyLong_Check(protocol)) { PyErr_SetString(PyExc_TypeError,"Expected pickle protocol number"); return nullptr; }
    auto* container=reinterpret_cast<SPELLdtaContainerObject*>(self)->container;
    if (!container) { PyErr_SetString(PyExc_RuntimeError,"Uninitialized DataContainer"); return nullptr; }
    Owned name(stateString(container->getContainerName())), attributes(pythonState(self)), values(PyDict_Copy(container->getDict()));
    if (!name.get() || !attributes.get() || !values.get()) return nullptr;
    Owned state(Py_BuildValue("(iOOOO)",1,name.get(),container->areNotificationsEnabled() ? Py_True : Py_False,
        values.get(),attributes.get()));
    return state.get() ? reduceNative(self,"_checkpoint_new_container",state.get()) : nullptr;
}
PyObject* containerSetState(PyObject* self,PyObject* state) {
    int version; PyObject *name,*notifications,*values,*attributes;
    if (!PyTuple_Check(state) || !PyArg_ParseTuple(state,"iOOOO",&version,&name,&notifications,&values,&attributes)) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError,"Invalid container checkpoint state"); return nullptr;
    }
    std::string text;
    if (version!=1 || !PyBool_Check(notifications)) { PyErr_SetString(PyExc_ValueError,"Invalid container checkpoint version or notification flag"); return nullptr; }
    if (!textState(name,text) || !checkPythonState(attributes)) return nullptr;
    auto* container=reinterpret_cast<SPELLdtaContainerObject*>(self)->container;
    if (!container) { PyErr_SetString(PyExc_ValueError,"Uninitialized checkpoint container"); return nullptr; }
    try { container->restoreSnapshot(text,values,notifications==Py_True); }
    catch (const SPELLcoreException& error) { return checkpointError(error); }
    if (!applyPythonState(self,attributes)) return nullptr;
    Py_RETURN_NONE;
}
PyObject* newCheckpointObject(PyObject* type,const char* name) {
    Owned base(nativeType(name)); if (!base.get()) return nullptr;
    if (!PyType_Check(type) || !PyType_Check(base.get())
            || !PyType_IsSubtype(reinterpret_cast<PyTypeObject*>(type),reinterpret_cast<PyTypeObject*>(base.get()))) {
        PyErr_SetString(PyExc_TypeError,"Invalid checkpoint allocation type"); return nullptr;
    }
    Owned result(reinterpret_cast<PyTypeObject*>(type)->tp_alloc(reinterpret_cast<PyTypeObject*>(type),0));
    if (!result.get()) return nullptr;
    try {
        if (std::string(name)=="Var") reinterpret_cast<SPELLdtaVariableObject*>(result.get())->var=new SPELLdtaVariable(nullptr);
        else {
            auto* object=reinterpret_cast<SPELLdtaContainerObject*>(result.get());
            object->container=new SPELLdtaContainer();
            object->container->setOwner(result.get());
        }
    } catch (const SPELLcoreException& error) { return checkpointError(error); }
    return Py_NewRef(result.get());
}
PyObject* newCheckpointVariable(PyObject*,PyObject* type) { return newCheckpointObject(type,"Var"); }
PyObject* newCheckpointContainer(PyObject*,PyObject* type) { return newCheckpointObject(type,"DataContainer"); }
PyMethodDef dtaCheckpointModuleMethods[] = {
    {"_checkpoint_new_var",newCheckpointVariable,METH_O,nullptr},
    {"_checkpoint_new_container",newCheckpointContainer,METH_O,nullptr},
    {nullptr,nullptr,0,nullptr}
};
}
