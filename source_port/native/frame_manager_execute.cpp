// SPDX-License-Identifier: GPL-3.0-or-later
const SPELLexecutionResult SPELLframeManager::execute()
{
    SPELLsafePythonOperations operations("SPELLframeManager::execute");
    if (!m_code || !m_initialFrame)
        THROW_EXCEPTION("Cannot execute procedure", "No compiled procedure", SPELL_ERROR_EXECUTION);
    SPELLerror::instance().clearErrors();
    m_status = EXECUTION_SUCCESS;
    if (m_resumePending) {
        SPELLpython313::Owned result(m_warmStart->resume());
        m_resumePending=false;
        checkRuntimeError();
        return m_status;
    }
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
