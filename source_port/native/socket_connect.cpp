// SPDX-License-Identifier: GPL-3.0-or-later
SPELLsocket* SPELLsocket::connect(const std::string& server,const int& port,
                                const std::atomic_bool* cancelled)
{
    const auto stopped=[&] { return cancelled && cancelled->load(); };
    if (stopped()) throw SPELLipcError("Connection cancelled");
    sockaddr_in address{};
    address.sin_family=AF_INET; address.sin_port=htons(port);
    // Native CIF connections use numeric loopback. Hostname resolution remains
    // a system resolver call; the TCP connect itself has a bounded deadline.
    if (inet_pton(AF_INET,server.c_str(),&address.sin_addr)!=1) {
        addrinfo hints{}; hints.ai_family=AF_INET; hints.ai_socktype=SOCK_STREAM;
        addrinfo* resolved=nullptr;
        const int result=getaddrinfo(server.c_str(),nullptr,&hints,&resolved);
        if (result!=0) throw SPELLipcError("Cannot resolve server host");
        address.sin_addr=reinterpret_cast<sockaddr_in*>(resolved->ai_addr)->sin_addr;
        freeaddrinfo(resolved);
    }
    int fd=::socket(AF_INET,SOCK_STREAM|SOCK_CLOEXEC|SOCK_NONBLOCK,0);
    if (fd<0) throw SPELLipcError("Error on socket creation");
    SPELLsocketOwnedFd ownership(fd);
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
    int result=::connect(fd,reinterpret_cast<sockaddr*>(&address),sizeof(address));
    if (result<0 && errno!=EINPROGRESS) throw SPELLipcError("Error on socket connect: errno "+ISTR(errno));
    while (result<0) {
        if (stopped()) throw SPELLipcError("Connection cancelled");
        if (std::chrono::steady_clock::now()>=deadline) throw SPELLipcError("Connection timed out");
        pollfd pending{fd,POLLOUT,0};
        const int available=::poll(&pending,1,100);
        if (available<0 && errno==EINTR) continue;
        if (available<0) throw SPELLipcError("Connection poll failed");
        if (available==0) continue;
        int error=0; socklen_t length=sizeof(error);
        if (getsockopt(fd,SOL_SOCKET,SO_ERROR,&error,&length)!=0 || error!=0)
            throw SPELLipcError("Error on socket connect: errno "+ISTR(error));
        result=0;
    }
    if (stopped()) throw SPELLipcError("Connection cancelled");
    if (fcntl(fd,F_SETFL,fcntl(fd,F_GETFL)&~O_NONBLOCK)<0)
        throw SPELLipcError("Cannot configure connected socket");
    auto* connection=new SPELLsocket(fd,"spell",{});
    ownership.release(); return connection;
}

