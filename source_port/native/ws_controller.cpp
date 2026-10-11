// SPDX-License-Identifier: GPL-3.0-or-later
#include "SPELL_WS/SPELLwsWarmStartImpl.H"
#include "SPELL_WS/SPELLwsFrame.H"
#include "SPELL_WS/SPELLcontinuation313.H"
#include "SPELL_WS/SPELLcontinuationCodec.H"
#include "SPELL_SYN/SPELLmonitor.H"
#include <memory>

SPELLwsWarmStartImpl::SPELLwsWarmStartImpl()
    : m_topFrame(nullptr), m_recursionDepth(0), m_lastState(nullptr), m_resuming(false) {}
SPELLwsWarmStartImpl::~SPELLwsWarmStartImpl() { reset(); }
void SPELLwsWarmStartImpl::initialize(const SPELLwsStartupInfo& info) {
    if (info.workingMode == MODE_UNINIT)
        THROW_EXCEPTION("Cannot initialize warm start", "Working mode is not set", SPELL_ERROR_WSTART);
    reset();
    m_startup = info;
    m_persistentFile = info.persistentFile.empty() ? "" : info.persistentFile+".wsp";
    m_recoveryFile = info.recoveryFile.empty() ? "" : info.recoveryFile+".wsp";
}
void SPELLwsWarmStartImpl::reset() {
    for (auto* frame: m_frames) delete frame;
    m_frames.clear(); m_topFrame=nullptr; m_recursionDepth=0;
    Py_CLEAR(m_lastState); m_resuming=false;
}
void SPELLwsWarmStartImpl::cleanup() {
    for (auto* frame: m_frames) frame->cleanup();
    if (!m_persistentFile.empty()) {
        unlink(m_persistentFile.c_str());
        unlink((m_persistentFile+"_READ").c_str());
        unlink((m_persistentFile+"_WRITE").c_str());
    }
    reset();
}
void SPELLwsWarmStartImpl::notifyCall(const std::string& id, PyFrameObject* frame) {
    if (getWorkingMode()==MODE_DISABLED) return;
    if (m_topFrame && m_topFrame->getFrameObject()==frame) return;
    if (m_frames.size()>=128)
        THROW_EXCEPTION("Cannot checkpoint procedure", "More than 128 caller frames", SPELL_ERROR_WSTART);
    if (m_topFrame) {
        int delta=SPELLcontinuation313::callerOffset(m_topFrame->getFrameObject(),frame);
        if (delta<0) {
            if (!PyErr_ExceptionMatches(PyExc_NotImplementedError)) SPELLpythonHelper::instance().checkError();
            // Ordinary execution may enter a class body or C callback. Track
            // that boundary, and reject attempts to publish a checkpoint there.
            PyErr_Clear();
        }
        if (delta>=0) m_topFrame->eventLine(); // C boundaries may hide the parent's live stack pointer
        m_topFrame->setReturnOffset(delta);
    }
    addFrame(id,frame);
}
void SPELLwsWarmStartImpl::notifyReturn() {
    // One return removes one caller, never the whole nested stack.
    if (m_frames.size()>1) removeTopFrame();
}
void SPELLwsWarmStartImpl::notifyLine() {
    if (getWorkingMode()==MODE_DISABLED) return;
    if (!m_topFrame) THROW_EXCEPTION("Cannot update warm start", "No active frame", SPELL_ERROR_WSTART);
    m_topFrame->eventLine();
    SPELLpython313::Owned state(captureChain());
    Py_XSETREF(m_lastState,Py_NewRef(state.get()));
    if (getWorkingMode()==MODE_ON_LINE) saveState();
}
void SPELLwsWarmStartImpl::notifyStage() {
    if (getWorkingMode()==MODE_ON_STEP) saveState();
}
PyObject* SPELLwsWarmStartImpl::captureChain() {
    if (m_frames.empty()) THROW_EXCEPTION("Cannot checkpoint procedure", "No active frames", SPELL_ERROR_WSTART);
    SPELLpython313::Owned chain(PyList_New(0));
    if (!chain.get()) SPELLpythonHelper::instance().checkError();
    for (auto it=m_frames.rbegin(); it!=m_frames.rend(); ++it) {
        if (it==m_frames.rbegin() || (*it)->getReturnOffset()>=0) (*it)->refresh();
        PyObject* state=(*it)->getState();
        if (!state) THROW_EXCEPTION("Cannot checkpoint procedure", "Frame has no saved state", SPELL_ERROR_WSTART);
        int delta=it==m_frames.rbegin() ? 0 : (*it)->getReturnOffset();
        SPELLpython313::Owned row(Py_BuildValue("(Oi)",state,delta));
        if (!row.get() || PyList_Append(chain.get(),row.get())<0) SPELLpythonHelper::instance().checkError();
    }
    return Py_NewRef(chain.get());
}
void SPELLwsWarmStartImpl::saveState() {
    if (getWorkingMode()==MODE_DISABLED || m_persistentFile.empty())
        THROW_EXCEPTION("Cannot checkpoint procedure", "Persistent warm start is not configured", SPELL_ERROR_WSTART);
    SPELLmonitor lock(m_lock);
    SPELLpython313::Owned state(captureChain());
    SPELLpython313::Owned codec(SPELLcontinuationCodec::module()), core(SPELLcontinuation313::module());
    if (!core.get()) SPELLpythonHelper::instance().checkError();
    SPELLpython313::Owned valid(PyObject_CallMethod(codec.get(),"validate_chain","OO",state.get(),core.get()));
    if (!valid.get()) SPELLpythonHelper::instance().checkError();
    SPELLcontinuationCodec::write(m_persistentFile,m_startup.procedureFile,state.get());
    Py_XSETREF(m_lastState,Py_NewRef(state.get()));
}
void SPELLwsWarmStartImpl::installChain(PyObject* state) {
    SPELLpython313::Owned codec(SPELLcontinuationCodec::module()), core(SPELLcontinuation313::module());
    if (!core.get()) SPELLpythonHelper::instance().checkError();
    SPELLpython313::Owned valid(PyObject_CallMethod(codec.get(),"validate_chain","OO",state,core.get()));
    if (!valid.get()) SPELLpythonHelper::instance().checkError();
    std::vector<std::unique_ptr<SPELLwsFrame>> next;
    SPELLwsStartupInfo memory(m_startup);
    memory.performRecovery=false; memory.persistentFile=""; memory.recoveryFile="";
    for (Py_ssize_t index=PyList_GET_SIZE(state); index>0; --index) {
        PyObject* row=PyList_GET_ITEM(state,index-1);
        PyObject* saved=PyTuple_GET_ITEM(row,0);
        SPELLpython313::Owned view(reinterpret_cast<PyObject*>(SPELLcontinuation313::inspection(saved)));
        if (!view.get()) SPELLpythonHelper::instance().checkError();
        auto frame=std::make_unique<SPELLwsFrame>("restored-"+std::to_string(next.size()),memory,next.size(),
            reinterpret_cast<PyFrameObject*>(view.get()));
        frame->setState(saved);
        frame->setReturnOffset(PyLong_AsLong(PyTuple_GET_ITEM(row,1)));
        next.push_back(std::move(frame));
    }
    // Prepare every frame before replacing the previously usable graph.
    for (auto* frame: m_frames) delete frame;
    m_frames.clear();
    for (auto& frame: next) m_frames.push_back(frame.release());
    m_topFrame=m_frames.back(); m_recursionDepth=m_frames.size();
    Py_XSETREF(m_lastState,Py_NewRef(state));
}
PyFrameObject* SPELLwsWarmStartImpl::restoreState() {
    if (m_recoveryFile.empty()) THROW_EXCEPTION("Cannot restore procedure", "No recovery path", SPELL_ERROR_WSTART);
    SPELLpython313::Owned state(SPELLcontinuationCodec::read(m_recoveryFile,m_startup.procedureFile));
    installChain(state.get());
    m_startup.performRecovery=false;
    return reinterpret_cast<PyFrameObject*>(Py_NewRef(m_topFrame->getFrameObject()));
}
PyFrameObject* SPELLwsWarmStartImpl::fixState() {
    if (!m_lastState) THROW_EXCEPTION("Cannot recover procedure", "No saved line state", SPELL_ERROR_WSTART);
    SPELLpython313::Owned saved(Py_NewRef(m_lastState));
    installChain(saved.get());
    return reinterpret_cast<PyFrameObject*>(Py_NewRef(m_topFrame->getFrameObject()));
}
std::vector<PyFrameObject*> SPELLwsWarmStartImpl::getFrames() const {
    std::vector<PyFrameObject*> result;
    for (auto* frame: m_frames) result.push_back(frame->getFrameObject());
    return result; // borrowed inspection/live references, root first
}
bool SPELLwsWarmStartImpl::rebindPending(PyFrameObject* frame) {
    if (!m_resuming || !m_topFrame || !m_topFrame->isPending()) return false;
    SPELLpython313::FrameCode expected(m_topFrame->getFrameObject()), actual(frame);
    if (expected.get()!=actual.get()) THROW_EXCEPTION("Cannot resume procedure", "Unexpected resumed code", SPELL_ERROR_WSTART);
    m_topFrame->rebind(frame);
    return true;
}
PyObject* SPELLwsWarmStartImpl::skipCaller(PyObject* capsule, PyObject*) {
    auto* self=static_cast<SPELLwsWarmStartImpl*>(PyCapsule_GetPointer(capsule,"SPELL.ws.resume"));
    if (!self) return nullptr;
    SPELLpython313::Owned frame(Py_NewRef(self->m_topFrame->getFrameObject()));
    auto* thread=PyThreadState_Get();
    if (thread->c_tracefunc) {
        // An unhandled child exception skips this logical caller. Its saved
        // inspection frame is used only to report stack departure.
        PyThreadState_EnterTracing(thread);
        int result=thread->c_tracefunc(thread->c_traceobj,reinterpret_cast<PyFrameObject*>(frame.get()),PyTrace_RETURN,Py_None);
        PyThreadState_LeaveTracing(thread);
        if (result<0) return nullptr;
    } else self->notifyReturn();
    Py_RETURN_NONE;
}
PyObject* SPELLwsWarmStartImpl::resume() {
    if (!m_lastState) { PyErr_SetString(PyExc_RuntimeError,"No restored continuation"); return nullptr; }
    SPELLpython313::Owned saved(Py_NewRef(m_lastState));
    SPELLpython313::Owned codec(SPELLcontinuationCodec::module()), core(SPELLcontinuation313::module());
    if (!core.get()) return nullptr;
    SPELLpython313::Owned capsule(PyCapsule_New(this,"SPELL.ws.resume",nullptr));
    static PyMethodDef skip={"skip_caller",skipCaller,METH_VARARGS,nullptr};
    SPELLpython313::Owned callback(capsule.get() ? PyCFunction_New(&skip,capsule.get()) : nullptr);
    if (!callback.get()) return nullptr;
    m_resuming=true;
    PyObject* result=PyObject_CallMethod(codec.get(),"resume_saved","OOO",saved.get(),core.get(),callback.get());
    m_resuming=false;
    return result;
}
void SPELLwsWarmStartImpl::addFrame(const std::string& id,PyFrameObject* frame) {
    SPELLwsStartupInfo memory(m_startup);
    memory.performRecovery=false; memory.persistentFile=""; memory.recoveryFile="";
    auto next=std::make_unique<SPELLwsFrame>(id,memory,m_frames.size(),frame);
    m_frames.push_back(next.get()); m_topFrame=next.release(); m_recursionDepth=m_frames.size();
}
void SPELLwsWarmStartImpl::removeTopFrame() {
    if (m_frames.empty()) return;
    delete m_frames.back(); m_frames.pop_back();
    m_topFrame=m_frames.empty() ? nullptr : m_frames.back();
    m_recursionDepth=m_frames.size();
}
