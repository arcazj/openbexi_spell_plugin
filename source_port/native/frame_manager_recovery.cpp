// SPDX-License-Identifier: GPL-3.0-or-later
void SPELLframeManager::restoreState() {
    if (!m_warmStart) THROW_EXCEPTION("Cannot restore state", "Warm start mechanism unavailable", SPELL_ERROR_WSTART);
    SPELLpython313::Owned view(reinterpret_cast<PyObject*>(m_warmStart->restoreState()));
    rebuildRecoveredModels(reinterpret_cast<PyFrameObject*>(view.get()));
}
void SPELLframeManager::fixState() {
    if (!m_warmStart) THROW_EXCEPTION("Cannot fix state", "Warm start mechanism unavailable", SPELL_ERROR_WSTART);
    SPELLpython313::Owned view(reinterpret_cast<PyObject*>(m_warmStart->fixState()));
    rebuildRecoveredModels(reinterpret_cast<PyFrameObject*>(view.get()));
}
void SPELLframeManager::rebuildRecoveredModels(PyFrameObject* top) {
    for (const auto& entry:m_modelMap) delete entry.second;
    m_modelMap.clear(); m_modelKeys.clear(); m_traceMap.clear();
    m_model=nullptr; m_currentFrame=nullptr;
    Py_XSETREF(m_initialFrame,reinterpret_cast<PyFrameObject*>(Py_NewRef(top)));
    int callLine=0;
    for (auto* frame:m_warmStart->getFrames()) {
        createFrameModel(callLine,frame);
        callLine=PyFrame_GetLineNumber(frame);
    }
    if (!m_model) THROW_EXCEPTION("Cannot restore state", "Restored stack is empty", SPELL_ERROR_WSTART);
    m_inError=false;
    m_terminated=false;
    m_resumePending=true;
}
//=============================================================================
