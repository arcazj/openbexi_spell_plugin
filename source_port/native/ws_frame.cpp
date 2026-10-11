// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_WS/SPELLwsFrame.H"
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include <memory>

SPELLwsFrame::SPELLwsFrame(const std::string& id, const SPELLwsStartupInfo& info, unsigned int depth, PyFrameObject* frame)
    : m_codeId(id), m_frame(nullptr), m_static(nullptr), m_dynamic(nullptr), m_pending(info.performRecovery)
{
    auto stat = std::make_unique<SPELLwsStaticData>(info,depth,frame);
    SPELLpython313::Owned owner(info.performRecovery ? reinterpret_cast<PyObject*>(stat->restore()) : Py_XNewRef(frame));
    if (!owner.get()) THROW_EXCEPTION("Cannot initialize frame", "Missing frame", SPELL_ERROR_WSTART);
    auto dyn = std::make_unique<SPELLwsDynamicData>(info,depth,reinterpret_cast<PyFrameObject*>(owner.get()));
    if (info.performRecovery) {
        dyn->restore();
        owner.reset(reinterpret_cast<PyObject*>(dyn->recover()));
        dyn->rebind(reinterpret_cast<PyFrameObject*>(owner.get()));
        stat->rebind(reinterpret_cast<PyFrameObject*>(owner.get()));
    }
    m_frame = reinterpret_cast<PyFrameObject*>(Py_NewRef(owner.get()));
    m_static = stat.release(); m_dynamic = dyn.release();
    m_lastInstruction = PyFrame_GetLasti(m_frame);
    m_lastLine = PyFrame_GetLineNumber(m_frame);
}
SPELLwsFrame::~SPELLwsFrame() { delete m_dynamic; delete m_static; Py_XDECREF(m_frame); }
void SPELLwsFrame::eventLine() {
    if (m_pending) THROW_EXCEPTION("Cannot update checkpoint", "Frame is an inspection view", SPELL_ERROR_WSTART);
    m_lastInstruction = PyFrame_GetLasti(m_frame);
    m_lastLine = PyFrame_GetLineNumber(m_frame);
    m_dynamic->update();
}
void SPELLwsFrame::refresh() { if (!m_pending) m_dynamic->refresh(); }
void SPELLwsFrame::cleanup() { m_dynamic->cleanup(); m_static->cleanup(); }
void SPELLwsFrame::fixState(PyThreadState*, bool) {
    // Recovery produces an inspection view. Live evaluation is performed by
    // the continuation engine, never by rewriting the interpreter thread.
    PyFrameObject* view = m_dynamic->recover();
    Py_SETREF(m_frame,view);
    m_dynamic->rebind(view);
    m_static->rebind(view);
    m_pending = true;
}
void SPELLwsFrame::reset() { m_dynamic->reset(); }
void SPELLwsFrame::saveState() { m_dynamic->save(); }
void SPELLwsFrame::setState(PyObject* state) {
    m_dynamic->setState(state);
    fixState(nullptr,false);
}
void SPELLwsFrame::rebind(PyFrameObject* frame) {
    Py_SETREF(m_frame,reinterpret_cast<PyFrameObject*>(Py_NewRef(frame)));
    m_static->rebind(frame); m_dynamic->rebind(frame);
    m_pending = false;
}
PyObject* SPELLwsFrame::getState() const { return m_dynamic->getState(); }
