// SPDX-License-Identifier: GPL-3.0-or-later
// Private candidate only. Original v0.7 binaries are preserved.
#include "admission_ipc.H"
#include "mutation_policy.H"
#include "terminal_gate.H"
#include <fcntl.h>
#include <cstdio>
#include <atomic>

static void v08_hold_before_consumption_probe(const ExecutorCommand& command)
{
    const char* probe = std::getenv("OPENBEXI_V08_CONSUMPTION_PROBE");
    const char* owner = std::getenv("OPENBEXI_V08_OWNER_STEP_PROBE");
    if (!probe && !owner) return;
    bool owner_hold = false;
    if (owner) {
        if (probe || std::strcmp(owner, "1") != 0)
            throw std::runtime_error("Native owner probe configuration differs");
        if (command.id != "CMD_STEP" || !command.v08External) return;
        static std::atomic<unsigned> steps{0};
        owner_hold = ++steps == 2;
        if (!owner_hold) return;
        probe = owner;
    }
    if (std::strcmp(probe, "1") != 0)
        throw std::runtime_error("Native consumption probe configuration differs");
    // Qualification-only hold at actual command consumption, BEFORE opening
    // the authenticated channel or starting its ordinary four-second deadline.
    // This path can only delay/deny; it never bypasses the live authority check.
    int marker = open(owner_hold ? "/workspace/owner-awaiting" : "/workspace/consume-awaiting", O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (marker < 0) throw std::runtime_error("Native consumption probe marker unavailable");
    const auto written = write(marker, "x", 1);
    const int closed = close(marker);
    if (written != 1 || closed != 0)
        throw std::runtime_error("Native consumption probe marker uncertain");
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(35);
    while (access(owner_hold ? "/control/owner-continue" : "/control/consume-continue", F_OK) != 0) {
        if (errno != ENOENT || std::chrono::steady_clock::now() >= deadline)
            throw std::runtime_error("Native consumption probe hold expired");
        usleep(20000);
    }
}

// The native handler returning does not settle background execution/driver
// effects, callbacks or descendants. This is an observation, never a barrier.
static void v08_report_native_disposition(const std::string& instance,
                                          const ExecutorCommand& command,
                                          const char* disposition) noexcept
{
    if (!command.v08External) return;  // Original internal safety operations.
    try {
        if (!v08_command_supported(command.id) || command.v08Request.empty())
            throw std::runtime_error("Native mailbox disposition not admitted");
        v08_native_request({
            {"schema", "openbexi.native-disposition/1"},
            {"instance_id", instance},
            {"request_id", command.v08Request},
            {"command", command.id},
            {"disposition", disposition}
        });
    } catch (...) {
        // A failed report retains an uncertain hold; never replay a command.
        std::fprintf(stderr, "V08_NATIVE_DISPOSITION_UNCERTAIN\n");
    }
}

static void v08_consume_native_run(const std::string& instance, const ExecutorCommand& command)
{
    if (v08_terminal_command(command.id) && command.v08External) {
        // This second, durable one-shot stage rejects copied mailbox entries,
        // stale owners and a command that bypassed CIF preprocessing.
        v08_terminal_authorize(instance, command.id, command.v08Request, "execute");
        return;
    }
    // Never let a copied/deferred external command evade the owner inventory.
    // Original native internal safety commands are not owner commands.
    if (v08_external_command_disabled(command.id, command.v08External))
        throw std::runtime_error("Native external mutation denied");
    if (command.id != "CMD_RUN" &&
        (!(command.id == "CMD_STEP" || command.id == "CMD_PAUSE") || !command.v08External)) return;
    if (command.v08Request.empty())
        throw std::runtime_error("Native RUN consumption has no admission identity");
    v08_hold_before_consumption_probe(command);
    v08_native_request({
        {"schema", "openbexi.native-consume/1"},
        {"instance_id", instance},
        {"request_id", command.v08Request},
        {"command", command.id}
    });
}
