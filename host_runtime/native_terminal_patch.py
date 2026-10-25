"""Exact-composition opt-in native ABORT/CLOSE authorization before CIF effects.

The existing cryptographic owner grant is consumed by Context before the original
CIF can cancel a prompt or set closing. An internal single-use ticket carries that
decision through the original mailbox; internal safety commands are unchanged.
"""

# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from pathlib import Path

PREIMAGES = {
    "include/SPELL_CIFS/SPELLserverCif.H": "ae6eccb88af5db4520d3c81a96c946a4b11e741c63a2d439ef0f78ce06c081f6",
    "lib/SPELL_CIFS/src/SPELLserverCif.C": "64590ef91857fba67252aa865377aae1057861b97643eb2e6231463f6413af90",
}


def patch_terminal_tree(source):
    source = Path(source)
    paths = {name: source / name for name in PREIMAGES}
    if any(
        hashlib.sha256(path.read_bytes()).hexdigest() != PREIMAGES[name]
        for name, path in paths.items()
    ):
        raise ValueError("Native terminal composed preimage differs")
    header = paths["include/SPELL_CIFS/SPELLserverCif.H"]
    unit = paths["lib/SPELL_CIFS/src/SPELLserverCif.C"]
    head, text = header.read_text(), unit.read_text()

    def replace(before, after):
        nonlocal text
        if text.count(before) != 1:
            raise ValueError("Native terminal boundary differs: " + before[:80])
        text = text.replace(before, after)

    declaration = "bool cancelPrompt(const SPELLipcMessage* ownerReply = nullptr);"
    if head.count(declaration) != 1:
        raise ValueError("Native terminal prompt signature differs")
    head = head.replace(
        declaration,
        "bool cancelPrompt(const SPELLipcMessage* ownerReply = nullptr, const std::string* terminalPrompt = nullptr);",
    )
    replace(
        '#include "/candidate/prompt_gate.H"',
        '#include "/candidate/prompt_gate.H"\n#include "/candidate/terminal_gate.H"',
    )
    replace(
        "void SPELLserverCif::processMessage( const SPELLipcMessage& msg )\n{\n",
        """void SPELLserverCif::processMessage( const SPELLipcMessage& msg )
{
    // Terminal commands must not even clear the IPC interruption state before
    // the one-use cryptographic grant has been consumed at the CIF boundary.
    if (v08_terminal_command(msg.getId())) {
        processMessageCommand(msg);
        return;
    }
""",
    )
    replace(
        "bool SPELLserverCif::cancelPrompt(const SPELLipcMessage* ownerReply)",
        "bool SPELLserverCif::cancelPrompt(const SPELLipcMessage* ownerReply, const std::string* terminalPrompt)",
    )
    replace(
        """    std::lock_guard<std::mutex> transition(spellPromptTransitionLock);
    if (ownerReply) {""",
        """    std::lock_guard<std::mutex> transition(spellPromptTransitionLock);
    if (terminalPrompt) {
        std::lock_guard<std::mutex> response(m_promptAnswerLock);
        if (m_v08PromptUncertain || m_v08PromptId != *terminalPrompt)
            throw std::runtime_error("Native terminal prompt changed during authorization");
    }
    if (ownerReply) {""",
    )
    replace(
        """void SPELLserverCif::processMessageCommand( const SPELLipcMessage& msg )
{
""",
        """void SPELLserverCif::processMessageCommand( const SPELLipcMessage& msg )
{
    const bool v08Terminal = v08_terminal_command(msg.getId());
    std::string v08TerminalPrompt;
    if (v08Terminal) {
        try {
            if (!v08_terminal_message_valid(msg.getId(), msg.getType() == MSG_TYPE_ONEWAY,
                                             msg.v08Fields(), getProcId()))
                throw std::runtime_error("Native terminal fields denied");
            {
                std::lock_guard<std::mutex> response(m_promptAnswerLock);
                if (m_v08PromptUncertain)
                    throw std::runtime_error("Native terminal prompt state uncertain");
                v08TerminalPrompt = m_v08PromptId;
            }
            std::string state;
            switch (SPELLexecutor::instance().getStatus()) {
                case STATUS_LOADED: state = "LOADED"; break;
                case STATUS_PAUSED: state = "PAUSED"; break;
                case STATUS_RUNNING: state = "RUNNING"; break;
                case STATUS_WAITING: state = "WAITING"; break;
                case STATUS_PROMPT: state = "PROMPT"; break;
                case STATUS_INTERRUPTED: state = "INTERRUPTED"; break;
                case STATUS_FINISHED: state = "FINISHED"; break;
                case STATUS_ERROR: state = "ERROR"; break;
                case STATUS_ABORTED: state = "ABORTED"; break;
                default: throw std::runtime_error("Native terminal status unqualified");
            }
            v08_admit_terminal_cif(getProcId(), msg, state, v08TerminalPrompt);
        } catch (const std::exception&) {
            v08_note_disabled_mutation(getProcId(), msg.getId());
            return;
        }
    }
""",
    )
    replace(
        """        if (cancelPrompt()) return;
        high_priority = true;""",
        """        try {
            if (cancelPrompt(nullptr, &v08TerminalPrompt)) {
                v08_terminal_prompt_handled(getProcId(), msg);
                return;
            }
        } catch (const std::exception&) {
            v08_note_disabled_mutation(getProcId(), msg.getId());
            return;
        }
        high_priority = true;""",
    )
    replace(
        """    SPELLexecutor::instance().command(cmd, high_priority);
}""",
        """    if (v08Terminal) {
        try { v08_queue_terminal(getProcId(), cmd.id, cmd.v08Request); }
        catch (const std::exception&) {
            v08_note_disabled_mutation(getProcId(), msg.getId());
            return;
        }
    }
    SPELLexecutor::instance().command(cmd, high_priority);
}""",
    )
    # Validate every anchor before changing either original source file.
    header.write_text(head)
    unit.write_text(text)
