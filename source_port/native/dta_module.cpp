// SPDX-License-Identifier: GPL-3.0-or-later
// Original DTA types and method tables, expressed with public heap-type slots.
#include "SPELL_UTIL/SPELLpython313.H"
static PyType_Slot containerSlots[] = {
    {Py_tp_dealloc, reinterpret_cast<void*>(SPELLdtaContainerObject_Dealloc)},
    {Py_tp_repr, reinterpret_cast<void*>(SPELLdtaContainerObject_Repr)},
    {Py_tp_str, reinterpret_cast<void*>(SPELLdtaContainerObject_Str)},
    {Py_tp_methods, SPELLdtaContainerObject_Methods},
    {Py_tp_traverse, reinterpret_cast<void*>(SPELLdtaContainerObject_Traverse)},
    {Py_tp_clear, reinterpret_cast<void*>(SPELLdtaContainerObject_Clear)},
    {Py_tp_iter, reinterpret_cast<void*>(SPELLdtaContainerObject_Iter)},
    {Py_tp_init, reinterpret_cast<void*>(SPELLdtaContainerObject_Init)},
    {Py_tp_new, reinterpret_cast<void*>(SPELLdtaContainerObject_New)},
    {Py_mp_length, reinterpret_cast<void*>(SPELLdtaContainerObject_DictLength)},
    {Py_mp_subscript, reinterpret_cast<void*>(SPELLdtaContainerObject_DictSubscript)},
    {Py_mp_ass_subscript, reinterpret_cast<void*>(SPELLdtaContainerObject_DictAssSub)},
    {0, nullptr}
};
static PyType_Slot variableSlots[] = {
    {Py_tp_dealloc, reinterpret_cast<void*>(SPELLdtaVariableObject_Dealloc)},
    {Py_tp_repr, reinterpret_cast<void*>(SPELLdtaVariableObject_Repr)},
    {Py_tp_str, reinterpret_cast<void*>(SPELLdtaVariableObject_Str)},
    {Py_tp_methods, SPELLdtaVariableObject_Methods},
    {Py_tp_init, reinterpret_cast<void*>(SPELLdtaVariableObject_Init)},
    {Py_tp_new, reinterpret_cast<void*>(SPELLdtaVariableObject_New)},
    {0, nullptr}
};
static PyType_Spec containerSpec = {"spell.lib.adapter.data.DataContainer", sizeof(SPELLdtaContainerObject), 0,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_IMMUTABLETYPE, containerSlots};
static PyType_Spec variableSpec = {"spell.lib.adapter.data.Var", sizeof(SPELLdtaVariableObject), 0,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_IMMUTABLETYPE, variableSlots};
MOD_INIT(libSPELL_DTA) {
    PyObject* module;
    MOD_DEF(module, MOD_NAME(libSPELL_DTA), "Module for SPELL data containers", dtaCheckpointModuleMethods);
    SPELLpython313::Owned container(PyType_FromSpec(&containerSpec)), variable(PyType_FromSpec(&variableSpec));
    if (!container.get() || !variable.get() || PyModule_AddObjectRef(module, "DataContainer", container.get())<0
            || PyModule_AddObjectRef(module, "Var", variable.get())<0) { Py_DECREF(module); return nullptr; }
    return module;
}
