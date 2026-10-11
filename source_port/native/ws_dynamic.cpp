// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_WS/SPELLwsDynamicData.H"
#include "SPELL_WS/SPELLcontinuation313.H"
#include "SPELL_WS/SPELLcontinuationCodec.H"

SPELLwsDynamicData::SPELLwsDynamicData(const SPELLwsStartupInfo& info, unsigned int depth, PyFrameObject* frame)
    : m_startup(info), m_frame(frame), m_state(nullptr), m_handled(nullptr), m_depth(depth)
{
    if (!frame) THROW_EXCEPTION("Cannot initialize frame data", "Missing frame", SPELL_ERROR_WSTART);
    if (!info.persistentFile.empty()) m_persistentFile = info.persistentFile+"_"+std::to_string(depth)+".wsd";
    if (!info.recoveryFile.empty()) m_recoveryFile = info.recoveryFile+"_"+std::to_string(depth)+".wsd";
}
SPELLwsDynamicData::~SPELLwsDynamicData() { Py_XDECREF(m_state); Py_XDECREF(m_handled); }
void SPELLwsDynamicData::reset() { Py_CLEAR(m_state); Py_CLEAR(m_handled); }
void SPELLwsDynamicData::update() {
    Py_XSETREF(m_handled,PyErr_GetHandledException());
    refresh();
}
void SPELLwsDynamicData::refresh() {
    PyObject* next = SPELLcontinuation313::snapshot(m_frame,m_handled);
    if (!next) SPELLpythonHelper::instance().checkError();
    Py_XSETREF(m_state,next);
}
void SPELLwsDynamicData::setState(PyObject* state) {
    SPELLpython313::Owned view(reinterpret_cast<PyObject*>(SPELLcontinuation313::inspection(state)));
    if (!view.get()) SPELLpythonHelper::instance().checkError();
    Py_XSETREF(m_state,Py_NewRef(state));
    PyObject* handled = PyTuple_GET_ITEM(state,3);
    Py_XSETREF(m_handled,handled == Py_None ? nullptr : Py_NewRef(handled));
}
PyFrameObject* SPELLwsDynamicData::recover() {
    if (!m_state) THROW_EXCEPTION("Cannot recover frame", "No saved line state", SPELL_ERROR_WSTART);
    PyFrameObject* view = SPELLcontinuation313::inspection(m_state);
    if (!view) SPELLpythonHelper::instance().checkError();
    return view;
}
void SPELLwsDynamicData::save() {
    if (!m_state) THROW_EXCEPTION("Cannot save frame", "No saved line state", SPELL_ERROR_WSTART);
    if (m_persistentFile.empty()) THROW_EXCEPTION("Cannot save frame", "No checkpoint path", SPELL_ERROR_WSTART);
    SPELLcontinuationCodec::write(m_persistentFile,m_startup.procedureFile,m_state);
}
void SPELLwsDynamicData::restore() {
    if (m_recoveryFile.empty()) THROW_EXCEPTION("Cannot restore frame", "No checkpoint path", SPELL_ERROR_WSTART);
    SPELLpython313::Owned state(SPELLcontinuationCodec::read(m_recoveryFile,m_startup.procedureFile));
    setState(state.get());
}
void SPELLwsDynamicData::cleanup() {
    if (!m_persistentFile.empty()) {
        unlink(m_persistentFile.c_str());
        unlink((m_persistentFile+"_READ").c_str());
        unlink((m_persistentFile+"_WRITE").c_str());
    }
}
