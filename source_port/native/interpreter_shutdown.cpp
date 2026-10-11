// SPDX-License-Identifier: GPL-3.0-or-later
void SPELLinterpreter::shutdown()
{
    // Join native workers before releasing their dependencies or Python. The
    // command main calls this without the GIL, so callbacks can finish.
    if (m_controllerStarted && m_controller) {
        m_controller->stop();
        static_cast<SPELLcontroller*>(m_controller)->join();
        m_controllerStarted=false;
    }
    delete m_scheduler; m_scheduler=nullptr;
    if (Py_IsInitialized()) {
        SPELLpython313::GIL gil;
        PyEval_SetTrace(nullptr,nullptr);
        delete m_frameManager; m_frameManager=nullptr;
        delete m_warmStart; m_warmStart=nullptr;
        SPELLexecutor::setInstance(nullptr);
        delete m_executor; m_executor=nullptr;
        delete m_callstack; m_callstack=nullptr;
        delete m_controller; m_controller=nullptr;
    }
    SPELLpythonHelper::instance().finalize();
}
