// SPDX-License-Identifier: GPL-3.0-or-later
// Channel teardown belongs to an owner thread, never to an input callback.
void SPELLipcClientInterface::connect(bool reconnect)
{
    std::lock_guard<std::mutex> lifecycle(m_lifecycleMutex);
    if (m_closed) throw SPELLipcError("Client is closed");
    SPELLipcChannel* previous=nullptr;
    SPELLsocket* previousSocket=nullptr;
    {
        SPELLmonitor lock(m_lock);
        if (m_connected && !reconnect) throw SPELLipcError("Client already connected");
        m_connected=false;
        previous=m_channel; previousSocket=m_socket;
        m_channel=nullptr; m_socket=nullptr;
    }
    cancelOutgoingRequests();
    if (previous) delete previous; else delete previousSocket;
    m_socket=SPELLsocket::connect(m_serverHost,m_serverPort,&m_closed);
    try {
        writeMyKey(reconnect ? m_clientKey : 0);
        m_clientKey=readMyKey();
        m_readyEvent.clear(); // publish the wait before the input thread starts
        {
            SPELLmonitor lock(m_lock);
            if (m_closed) throw SPELLipcError("Connection cancelled");
            m_channel=createChannel();
            m_connected=true;
            m_channel->connect();
        }
        waitReady();
        LOG_INFO(NAME + "Connected to " + m_serverHost + ":" + ISTR(m_serverPort));
    } catch (...) {
        SPELLipcChannel* failed=nullptr;
        SPELLsocket* failedSocket=nullptr;
        {
            SPELLmonitor lock(m_lock);
            m_connected=false;
            failed=m_channel; failedSocket=m_socket;
            m_channel=nullptr; m_socket=nullptr;
        }
        if (failed) delete failed; else delete failedSocket;
        throw;
    }
}

