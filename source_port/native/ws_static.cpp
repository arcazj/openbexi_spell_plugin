// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_WS/SPELLwsStaticData.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include <unistd.h>

SPELLwsStaticData::SPELLwsStaticData(const SPELLwsStartupInfo& info, unsigned int depth, PyFrameObject* frame)
    : m_startup(info), m_depth(depth), m_frame(frame), m_storage(nullptr)
{
    if (!info.persistentFile.empty()) m_persistentFile = info.persistentFile+"_"+std::to_string(depth)+".wss";
    if (!info.recoveryFile.empty()) m_recoveryFile = info.recoveryFile+"_"+std::to_string(depth)+".wss";
    if (info.performRecovery && !m_recoveryFile.empty())
        m_storage = new SPELLwsStorage(m_recoveryFile,SPELLwsStorage::MODE_READ);
    else if (!m_persistentFile.empty()) {
        m_storage = new SPELLwsStorage(m_persistentFile,SPELLwsStorage::MODE_WRITE);
        try { save(); } catch (...) { delete m_storage; throw; }
    }
}
SPELLwsStaticData::~SPELLwsStaticData() { delete m_storage; }
void SPELLwsStaticData::cleanup() {
    delete m_storage; m_storage = nullptr;
    if (!m_persistentFile.empty()) {
        unlink(m_persistentFile.c_str());
        unlink((m_persistentFile+"_READ").c_str());
        unlink((m_persistentFile+"_WRITE").c_str());
    }
}
PyFrameObject* SPELLwsStaticData::restore() {
    if (!m_storage || m_storage->getMode() != SPELLwsStorage::MODE_READ)
        THROW_EXCEPTION("Cannot restore static data", "Readable storage is required", SPELL_ERROR_WSTART);
    SPELLpython313::Owned code(m_storage->loadObject());
    if (!PyCode_Check(code.get()))
        THROW_EXCEPTION("Cannot restore static data", "Expected code object", SPELL_ERROR_WSTART);
    SPELLpython313::Owned globals(m_frame ? PyFrame_GetGlobals(m_frame) : PyDict_New());
    if (!globals.get()) SPELLpythonHelper::instance().checkError();
    PyFrameObject* view = PyFrame_New(PyThreadState_Get(),reinterpret_cast<PyCodeObject*>(code.get()),globals.get(),globals.get());
    if (!view) SPELLpythonHelper::instance().checkError();
    m_frame = view; // borrowed; returned owned reference belongs to frame controller
    delete m_storage; m_storage = nullptr;
    return view;
}
void SPELLwsStaticData::save() {
    if (!m_frame || !m_storage) THROW_EXCEPTION("Cannot save static data", "Frame and storage are required", SPELL_ERROR_WSTART);
    SPELLpython313::Owned code(reinterpret_cast<PyObject*>(PyFrame_GetCode(m_frame)));
    if (!code.get()) SPELLpythonHelper::instance().checkError();
    m_storage->storeObject(code.get());
}
