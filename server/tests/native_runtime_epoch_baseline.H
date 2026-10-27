// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_ADMISSION_IPC_H
#define OPENBEXI_V08_ADMISSION_IPC_H
#include <nlohmann/json.hpp>
#include "admission_channel.H"
#include <cstdlib>
#include <fstream>

static void v08_native_request(const nlohmann::json& body)
{
    nlohmann::json captured = body;
    const char* epochPath = std::getenv("OPENBEXI_V08_RUNTIME_EPOCH");
    if (epochPath) {
        std::ifstream stream(epochPath);
        std::string epoch;
        std::getline(stream, epoch);
        if (!stream || epoch.size() != 36 || stream.peek() != EOF)
            throw std::runtime_error("Native runtime epoch unavailable");
        captured["runtime_epoch"] = epoch;
    }
    const char* path = std::getenv("OPENBEXI_V08_ADMISSION_SOCKET");
    const char* agent = std::getenv("OPENBEXI_V08_AGENT_PID");
    if (!path || !agent || std::strlen(path) >= sizeof(sockaddr_un::sun_path))
        throw std::runtime_error("Native admission provider unavailable");
    v08_admission_exchange(path, agent, captured.dump() + "\n");
}
#endif
