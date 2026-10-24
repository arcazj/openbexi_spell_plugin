// SPDX-License-Identifier: GPL-3.0-or-later
// Private candidate only. Original v0.7 binaries are preserved.
#include "admission_ipc.H"
#include <fcntl.h>

static void v08_hold_before_consumption_probe()
{
    const char* probe = std::getenv("OPENBEXI_V08_CONSUMPTION_PROBE");
    if (!probe) return;
    if (std::strcmp(probe, "1") != 0)
        throw std::runtime_error("Native consumption probe configuration differs");
    // Qualification-only hold at actual command consumption, BEFORE opening
    // the authenticated channel or starting its ordinary four-second deadline.
    // This path can only delay/deny; it never bypasses the live authority check.
    int marker = open("/workspace/consume-awaiting", O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (marker < 0) throw std::runtime_error("Native consumption probe marker unavailable");
    const auto written = write(marker, "x", 1);
    const int closed = close(marker);
    if (written != 1 || closed != 0)
        throw std::runtime_error("Native consumption probe marker uncertain");
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(35);
    while (access("/control/consume-continue", F_OK) != 0) {
        if (errno != ENOENT || std::chrono::steady_clock::now() >= deadline)
            throw std::runtime_error("Native consumption probe hold expired");
        usleep(20000);
    }
}

static void v08_consume_native_run(const std::string& instance, const ExecutorCommand& command)
{
    if (command.id != "CMD_RUN") return;
    if (command.v08Request.empty())
        throw std::runtime_error("Native RUN consumption has no admission identity");
    v08_hold_before_consumption_probe();
    v08_native_request({
        {"schema", "openbexi.native-consume/1"},
        {"instance_id", instance},
        {"request_id", command.v08Request},
        {"command", "CMD_RUN"}
    });
}
