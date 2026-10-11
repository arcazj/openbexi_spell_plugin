// SPDX-License-Identifier: GPL-3.0-or-later
void SPELLframeManager::runScript(const std::string& script)
{
    SPELLsafePythonOperations operations("SPELLframeManager::runScript");
    if (!m_currentFrame)
        THROW_EXCEPTION("Cannot execute script", "No current frame", SPELL_ERROR_EXECUTION);
    SPELLpython313::Owned code(reinterpret_cast<PyObject*>(compileScript(script)));
    SPELLpython313::FrameGlobals globals(m_currentFrame);
    SPELLpython313::FrameLocals locals(m_currentFrame);
    if (!globals.get() || !locals.get()) SPELLpythonHelper::instance().checkError();
    SPELLpython313::Owned result(PyEval_EvalCode(code.get(), globals.get(), locals.get()));
    if (!result.get()) SPELLpythonHelper::instance().checkError();
    getModel().update();
}

//=============================================================================
