"""Exact-source, opt-in ABORT/CLOSE hooks before all native command effects.

The existing Context verifies immutable 256-bit owner capabilities. The CIF
must consume permission before cancelPrompt or setClosing; a copied command
must pass a second one-shot transition before reaching the controller handler.
Internal safety shutdowns retain original semantics and grant no external right.
"""

# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from pathlib import Path

PREIMAGES = {
    False: (
        "b93acc7e7d8c54f0c8e6825db20fe5fdc91dde01266f24df2f16923d7d10a006",
        "e78bdebd8493e6309380dfbc2bcb39ecd4f9554aeb50cd4089aad87da2ac5bc3",
    ),
    True: (
        "ae6eccb88af5db4520d3c81a96c946a4b11e741c63a2d439ef0f78ce06c081f6",
        "64590ef91857fba67252aa865377aae1057861b97643eb2e6231463f6413af90",
    ),
}


def patch_terminal_tree(source, *, prompts=False):
    source = Path(source)
    header = source / "include/SPELL_CIFS/SPELLserverCif.H"
    unit = source / "lib/SPELL_CIFS/src/SPELLserverCif.C"
    actual = tuple(hashlib.sha256(p.read_bytes()).hexdigest() for p in (header, unit))
    if actual != PREIMAGES[prompts]:
        raise ValueError("Native terminal composed preimage differs")
    head, text = header.read_text(), unit.read_text()

    def replace(before, after):
        nonlocal text
        if text.count(before) != 1:
            raise ValueError("Ambiguous native terminal boundary: " + before[:72])
        text = text.replace(before, after)

    declaration = "void processMessageCommand( const SPELLipcMessage& msg );"
    if head.count(declaration) != 1:
        raise ValueError("Ambiguous native terminal header")
    head = head.replace(
        declaration,
        declaration + "\n        void v08ProcessTerminal(const SPELLipcMessage& msg);",
    )
    replace(
        '#include "/candidate/mutation_gate.H"',
        '#include "/candidate/mutation_gate.H"\n#include "/candidate/terminal_gate.H"',
    )
    # Divert before even m_ipcInterruptionNotified is reset, and protect direct
    # calls to processMessageCommand as well as the ordinary incoming route.
    for signature, action in (
        (
            "void SPELLserverCif::processMessage( const SPELLipcMessage& msg )\n{\n",
            "processMessageCommand",
        ),
        (
            "void SPELLserverCif::processMessageCommand( const SPELLipcMessage& msg )\n{\n",
            "v08ProcessTerminal",
        ),
    ):
        replace(
            signature,
            signature
            + "    if (v08_terminal_command(msg.getId())) {\n"
            + "        "
            + action
            + "(msg);\n        return;\n    }\n",
        )
    text += """

// Terminal authority is consumed before any original command mutation. A
// genuine owner ABORT during a prompt retains the original scheduler path.
void SPELLserverCif::v08ProcessTerminal(const SPELLipcMessage& msg)
{
    try {
        if (!v08_terminal_message_valid(msg.getId(), msg.getType() == MSG_TYPE_ONEWAY,
                                        msg.v08Fields(), getProcId()))
            throw std::runtime_error("Native terminal fields or target differ");
        v08_terminal_authorize(getProcId(), msg.getId(), msg.get("V08ControlRequest"), "preprocess");
        ExecutorCommand cmd;
        cmd.id = msg.getId();
        cmd.v08External = true;
        cmd.v08Request = msg.get("V08ControlRequest");
        if (cmd.id == ExecutorMessages::MSG_CMD_ABORT) {
            // If the scheduler owns an active prompt cancellation it performs
            // the original abort transition; do NOT send a second abort.
            if (cancelPrompt()) return;
        } else if (cmd.id == ExecutorMessages::MSG_CMD_CLOSE) {
            SPELLmonitor guard(m_ipcLock);
            setClosing();
        }
        // Controller must durably admit terminal-execute before processing.
        SPELLexecutor::instance().command(cmd, true);
    } catch (const std::exception&) {
        // No retransmission or fall-through to the original unguarded path.
        v08_note_disabled_mutation(getProcId(), msg.getId());
    }
}
"""
    # Commit both files only after every preimage and anchor is verified.
    header.write_text(head)
    unit.write_text(text)
