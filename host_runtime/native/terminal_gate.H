// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_TERMINAL_GATE_H
#define OPENBEXI_V08_TERMINAL_GATE_H
#include <mutex>
#include <set>
#include <stdexcept>
#include <string>

inline bool v08_terminal_command(const std::string& id)
{
    return id == "CMD_ABORT" || id == "CMD_CLOSE";
}

// Called at the CIF before cancelPrompt(), setClosing(), or queue insertion.
// An ABORT cancels the current prompt of THIS exact member as part of aborting
// that member; it is not a prompt ANSWER/CANCEL grant or a completion receipt.
template<class Command, class Authorize>
void v08_admit_terminal_command(Command& command, bool native_terminal,
                                 Authorize authorize)
{
    if (!v08_terminal_command(command.id) || !command.v08External ||
        command.v08Request.empty() || command.v08TerminalAdmitted)
        throw std::runtime_error("Native terminal command identity denied");
    if ((command.id == "CMD_CLOSE") != native_terminal)
        throw std::runtime_error("Native terminal command state denied");
    // On timeout/lost acknowledgement the bit remains false and NO effect is
    // performed, even when Context persisted consumption. Never retry.
    authorize();
    command.v08TerminalAdmitted = true;
}

// A mailbox copy carries only in-process provenance, never a wire-supplied
// bit. Consume that continuation once; do not mint a second remote grant.
class V08TerminalContinuations
{
    std::mutex mutex;
    std::set<std::string> consumed;
public:
    template<class Command> void consume(const Command& command)
    {
        std::lock_guard<std::mutex> guard(mutex);
        if (!v08_terminal_command(command.id) || !command.v08External ||
            !command.v08TerminalAdmitted || command.v08Request.empty() ||
            consumed.size() >= 512 || !consumed.insert(command.v08Request).second)
            throw std::runtime_error("Native terminal continuation denied");
    }
};
#endif
