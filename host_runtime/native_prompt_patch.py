"""Exact-source prompt admission hooks, applied AFTER frozen source composition.

Does not replace the original condition-variable/scheduler synchronization.
Default-off runtime profile; authorization occurs before native selection.
"""

# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path


def patch_prompt_boundary(source):
    source = Path(source)
    header = source / "include/SPELL_CIFS/SPELLserverCif.H"
    unit = source / "lib/SPELL_CIFS/src/SPELLserverCif.C"
    h, s = header.read_text(), unit.read_text()

    def replace(text, before, after):
        if text.count(before) != 1:
            raise ValueError("Native prompt composed-source boundary differs")
        return text.replace(before, after)

    h = replace(
        h,
        "#define __SPELL_SERVER_CIF_H__",
        '#define __SPELL_SERVER_CIF_H__\n#include "/candidate/prompt_state.H"',
    )
    h = replace(
        h,
        "bool m_promptPending = false;",
        "bool m_promptPending = false;\n        V08PromptState m_v08Prompt;",
    )
    h = replace(
        h,
        "bool cancelPrompt();",
        "bool cancelPrompt();\n        bool cancelPrompt(const SPELLipcMessage* ownerReply);",
    )
    s = replace(
        s,
        '#include "/candidate/mutation_gate.H"',
        '#include "/candidate/mutation_gate.H"\n#include "/candidate/prompt_gate.H"',
    )
    guard = '    if (v08_message_disabled(msg.getId(), msg.hasField("ParentId") && !msg.get("ParentId").empty())) {'
    s = replace(
        s,
        guard,
        """    const bool promptReply = msg.getId() == "MSG_ANSWER" || msg.getId() == "MSG_CANCEL";
    if (v08_message_disabled(msg.getId(), msg.hasField("ParentId") && !msg.get("ParentId").empty())
        && !(promptReply && v08_prompts_enabled())) {""",
    )
    s = replace(
        s,
        """        if (m_promptPending && m_promptAnswer.isVoid())
        {
            m_promptAnswer = msg;""",
        """        if (m_promptPending && m_promptAnswer.isVoid())
        {
            if (!v08_select_prompt(getProcId(), m_v08Prompt, msg, "ANSWER")) {
                v08_note_disabled_mutation(getProcId(), msg.getId());
                return;
            }
            m_promptAnswer = msg;""",
    )
    s = replace(
        s,
        '    \tLOG_WARN("Prompt has been cancelled by client");\n    \tcancelPrompt();',
        '    \tLOG_WARN("Prompt has been cancelled by client");\n    \tcancelPrompt(&msg);',
    )
    s = replace(
        s,
        """        m_promptAnswer = VOID_MESSAGE;
        m_promptPending = true;
    }
    // Status publication""",
        """        m_promptAnswer = VOID_MESSAGE;
        m_promptPending = true;
        if (v08_prompts_enabled()) m_v08Prompt.open(v08_prompt_uuid());
    }
    if (v08_prompts_enabled()) {
        SPELLsafeThreadOperations ops("SPELLserverCif::register v08 prompt");
        try { v08_register_prompt(getProcId(), m_v08Prompt, m_promptMessage); }
        catch (const std::exception&) {
            std::lock_guard<std::mutex> response(m_promptAnswerLock);
            m_v08Prompt.outcome = "FAILED";
            m_v08Prompt.finish();
            m_promptPending = false;
            THROW_EXCEPTION("Native prompt denied", "Prompt registration unavailable", SPELL_ERROR_EXECUTION);
        }
    }
    // Status publication""",
    )
    s = replace(
        s,
        """bool SPELLserverCif::cancelPrompt()
{
    SPELLsafeThreadOperations""",
        """bool SPELLserverCif::cancelPrompt()
{
    return cancelPrompt(nullptr); // Original internal scheduler/abort path.
}

bool SPELLserverCif::cancelPrompt(const SPELLipcMessage* ownerReply)
{
    SPELLsafeThreadOperations""",
    )
    s = replace(
        s,
        """        if (!m_promptPending || !m_promptAnswer.isVoid()) return false;
        // Claim cancellation""",
        """        if (!m_promptPending || !m_promptAnswer.isVoid()) return false;
        if (ownerReply) {
            if (!v08_select_prompt(getProcId(), m_v08Prompt, *ownerReply, "CANCEL")) {
                v08_note_disabled_mutation(getProcId(), ownerReply->getId());
                return false;
            }
        } else {
            m_v08Prompt.internal_cancel(); // Never forge an owner cancellation receipt.
        }
        // Claim cancellation""",
    )
    s = replace(
        s,
        """        if (!m_promptAnswerReady.wait_until(response, deadline, answered)
            && m_promptAnswer.isVoid())""",
        """        if (m_v08Prompt.active) m_v08Prompt.bound_deadline(deadline);
        if (!m_promptAnswerReady.wait_until(response, deadline, answered)
            && m_promptAnswer.isVoid())""",
    )
    s = replace(
        s,
        """            // Use the same native option conversion as an explicit answer.
            m_promptAnswer = SPELLipcMessage""",
        """            // Use the same native option conversion as an explicit answer.
            if (m_v08Prompt.active) m_v08Prompt.timeout();
            m_promptAnswer = SPELLipcMessage""",
    )
    s = replace(
        s,
        """    // Late or duplicate answers cannot replace the selected result.
    m_promptPending = false;""",
        """    // Late or duplicate answers cannot replace the selected result.
    m_promptPending = false;
    const V08PromptState v08Completed(m_v08Prompt);
    m_v08Prompt.finish();""",
    )
    s = replace(
        s,
        """        SPELLexecutor::instance().getScheduler().finishPrompt();
    }
}""",
        """        SPELLexecutor::instance().getScheduler().finishPrompt();
    }
    // One safety-only receipt after the original scheduler transition.
    v08_close_prompt(getProcId(), v08Completed);
}""",
    )
    # All anchors validated before either file is overwritten.
    header.write_text(h)
    unit.write_text(s)
