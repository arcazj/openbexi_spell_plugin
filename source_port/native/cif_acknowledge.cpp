// SPDX-License-Identifier: GPL-3.0-or-later
void SPELLserverCif::sendAcknowledged(const SPELLipcMessage& message)
{
    while (!isClosing()) {
        unsigned long generation;
        {
            std::unique_lock<std::mutex> lock(m_reconnectMutex);
            if (!m_ready) {
                m_reconnectWake.wait_for(lock,std::chrono::milliseconds(50));
                continue;
            }
            generation=m_reconnectGeneration;
        }
        sendGUIMessage(message);
        // A disconnect between readiness and send invalidates the wait. Never
        // wait for an ACK to a message skipped during a disconnected interval.
        if (waitAcknowledge(message,generation)) return;
    }
}

bool SPELLserverCif::waitAcknowledge(const SPELLipcMessage& message,unsigned long generation)
{
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(static_cast<unsigned long long>(m_timeoutAcknowledgeSec)+1);
    const auto sequence=message.get(MessageField::FIELD_MSG_SEQUENCE);
    while (!isClosing()) {
        {
            std::lock_guard<std::mutex> state(m_reconnectMutex);
            if (!m_ready || generation!=m_reconnectGeneration) return false;
        }
        {
            SPELLmonitor lock(m_ackLock);
            const auto ack=std::find(m_ackSequences.begin(),m_ackSequences.end(),sequence);
            if (ack!=m_ackSequences.end()) { m_ackSequences.erase(ack);return true; }
        }
        if (std::chrono::steady_clock::now()>=deadline) {
            LOG_WARN("Acknowledge not received: "+message.dataStr());
            return false;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    return false;
}
