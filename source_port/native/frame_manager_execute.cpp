// SPDX-License-Identifier: GPL-3.0-or-later
const SPELLexecutionResult SPELLframeManager::execute()
{
    SPELLsafePythonOperations operations("SPELLframeManager::execute");
    if (!m_code || !m_initialFrame)
        THROW_EXCEPTION("Cannot execute procedure", "No compiled procedure", SPELL_ERROR_EXECUTION);
    if (m_resumePending)
        THROW_EXCEPTION("Cannot resume saved procedure", "Modern WS continuation integration is required", SPELL_ERROR_WSTART);
    SPELLerror::instance().clearErrors();
    m_status = EXECUTION_SUCCESS;
    // CPython must allocate the live evaluation frame. PyFrame_New creates an
    // inspection frame, which cannot be passed to the modern frame evaluator.
    SPELLpython313::FrameGlobals globals(m_initialFrame);
    SPELLpython313::FrameLocals locals(m_initialFrame);
    if (!globals.get() || !locals.get()) SPELLpythonHelper::instance().checkError();
    SPELLpython313::Owned result(PyEval_EvalCode(reinterpret_cast<PyObject*>(m_code), globals.get(), locals.get()));
    checkRuntimeError();
    return m_status;
}

//=============================================================================
