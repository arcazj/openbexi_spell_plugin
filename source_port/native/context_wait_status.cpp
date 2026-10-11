// SPDX-License-Identifier: GPL-3.0-or-later
bool SPELLexecutor::waitStatus(const SPELLexecutorStatus& status,unsigned int timeoutMsec)
{
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(timeoutMsec);
    for (;;) {
        // Arm before observing state: a transition after this clear is either
        // observed directly or retained as an event for the wait below.
        m_executorStatusEvent.clear();
        if (m_model.getStatus()==status) return false;
        const auto now=std::chrono::steady_clock::now();
        if (now>=deadline) return true;
        const auto remaining=std::chrono::duration_cast<std::chrono::milliseconds>(deadline-now).count();
        m_executorStatusEvent.wait(static_cast<unsigned long>(remaining+1));
    }
}
//=============================================================================
