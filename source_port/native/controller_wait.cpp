// SPDX-License-Identifier: GPL-3.0-or-later
// CPython line jumps run on the tracing thread; the original command handlers
// still perform validation, status transitions and mailbox acknowledgement.
void SPELLcontroller::doWait()
{
    if (m_abort || m_error || m_finished) return;
    m_wantPause=false;
    {
        std::lock_guard<std::mutex> guard(m_traceMutex);
        // Close may have signalled continuation before this pause took the
        // mutex. Never erase a terminal wakeup and park the tracing thread.
        if (m_abort || m_error || m_finished) return;
        m_traceContinue=false;
        m_execLock.clear();
        m_traceWaiting=true;
    }
    // Publish PAUSED only after the wakeup state is ready: a fast Run must not
    // lose its notification between this status and the wait below.
    if (!m_wantInterrupt) setStatus(STATUS_PAUSED);
    m_wantInterrupt=false;
    notifyBeforeWait();
    for (;;) {
        {
            SPELLsafeThreadOperations release("SPELLcontroller::doWait");
            m_execLock.wait();
        }
        std::unique_ptr<ExecutorCommand> command;
        {
            std::lock_guard<std::mutex> guard(m_traceMutex);
            m_execLock.clear();
            command=std::move(m_traceCommand);
        }
        if (command) {
            try { executeCommand(*command); }
            catch (...) {
                m_traceCommandDone.set();
                { std::lock_guard<std::mutex> guard(m_traceMutex); m_traceWaiting=false; }
                throw;
            }
        }
        {
            std::lock_guard<std::mutex> guard(m_traceMutex);
            if (m_traceContinue) {
                m_traceWaiting=false;
                if (command) m_traceCommandDone.set();
                break;
            }
            if (command) m_traceCommandDone.set();
        }
        // Rejected jumps remain paused. doContinue signals only an accepted
        // control operation, so failure never executes the guarded statement.
    }
    notifyAfterWait();
}

void SPELLcontroller::doContinue()
{
    std::lock_guard<std::mutex> guard(m_traceMutex);
    m_traceContinue=true;
    m_execLock.set();
}

//=============================================================================
