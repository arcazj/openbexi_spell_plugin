// SPDX-License-Identifier: GPL-3.0-or-later
void SPELLserverCif::processConnectionError(int,std::string error,std::string reason)
{
    if (isClosing()) return;
    m_ready=false;
    LOG_ERROR("IPC error: " + error + ": " + reason);
    {
        std::lock_guard<std::mutex> lock(m_reconnectMutex);
        ++m_reconnectGeneration;
        m_reconnectPending=true;
    }
    m_reconnectWake.notify_all();
}

void SPELLserverCif::reconnectLoop()
{
    std::unique_lock<std::mutex> lock(m_reconnectMutex);
    while (!m_reconnectStop) {
        m_reconnectWake.wait(lock,[&] { return m_reconnectStop || m_reconnectPending; });
        if (m_reconnectStop) return;
        auto generation=m_reconnectGeneration;
        m_reconnectPending=false;
        lock.unlock();
        // The input callback has returned before this owner destroys its channel.
        // pause() queues the original controller command on the executor thread.
        SPELLexecutor::instance().pause();
        switch (SPELLexecutor::instance().getStatus()) {
        case STATUS_FINISHED: case STATUS_PAUSED: case STATUS_ABORTED:
        case STATUS_ERROR: case STATUS_PROMPT: case STATUS_INTERRUPTED: break;
        default:
            SPELLexecutor::instance().getScheduler().raiseWarningEventToGCS(
                "Procedure lost SPELL Context, check and resume: "+getProcId());
        }
        while (!isClosing()) {
            try {
                LOG_WARN("Trying to reconnect on port " + ISTR(m_ifc->getServerPort()));
                m_ifc->connect(true);
                auto response=login();
                if (response.isVoid() || response.getType()==MSG_TYPE_ERROR)
                    throw SPELLipcError("Context reconnect login failed");
                processLogin(response);
                std::lock_guard<std::mutex> state(m_reconnectMutex);
                if (!m_reconnectStop && generation==m_reconnectGeneration && m_ifc->isConnected()) {
                    m_ready=true;
                    LOG_INFO("Successfully reconnected to context");
                    break;
                }
            } catch (const SPELLcoreException& error) {
                LOG_ERROR("Failed to reconnect: " + std::string(error.what()));
            } catch (const std::exception& error) {
                LOG_ERROR("Failed to reconnect: " + std::string(error.what()));
            }
            lock.lock();
            m_reconnectWake.wait_for(lock,std::chrono::seconds(5),[&] {
                return m_reconnectStop || m_reconnectPending;
            });
            generation=m_reconnectGeneration;
            m_reconnectPending=false;
            const bool stop=m_reconnectStop;
            lock.unlock();
            if (stop) break;
        }
        lock.lock();
    }
}

void SPELLserverCif::stopReconnect()
{
    setClosing();
    {
        std::lock_guard<std::mutex> lock(m_reconnectMutex);
        m_reconnectStop=true;
    }
    m_reconnectWake.notify_all();
    // During an incomplete reconnect, cancel a pending connect/handshake/login.
    // Normal connected shutdown retains logout before transport teardown.
    if (m_ifc && !m_ready) m_ifc->disconnect();
    if (m_reconnectThread.joinable()) m_reconnectThread.join();
}
