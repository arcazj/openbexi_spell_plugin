"""Opt-in exact-composition prompt hooks; no published runtime is enabled.

Keep the original transition/mailbox locks, timeout/default conversion and
scheduler. Authorization never holds the answer mutex. A timeout can win while
Context is consulted; a second local check prevents applying a late grant.
"""

# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from pathlib import Path

PREIMAGES = {
    "header": "b93acc7e7d8c54f0c8e6825db20fe5fdc91dde01266f24df2f16923d7d10a006",
    "unit": "e78bdebd8493e6309380dfbc2bcb39ecd4f9554aeb50cd4089aad87da2ac5bc3",
}


def patch_prompt_tree(source):
    source = Path(source)
    header = source / "include/SPELL_CIFS/SPELLserverCif.H"
    unit = source / "lib/SPELL_CIFS/src/SPELLserverCif.C"
    if (
        hashlib.sha256(header.read_bytes()).hexdigest() != PREIMAGES["header"]
        or hashlib.sha256(unit.read_bytes()).hexdigest() != PREIMAGES["unit"]
    ):
        raise ValueError("Native prompt composed preimage differs")
    head, text = header.read_text(), unit.read_text()

    def replace(before, after):
        nonlocal text
        if text.count(before) != 1:
            raise ValueError(
                "Native prompt composition boundary differs: " + before[:72]
            )
        text = text.replace(before, after)

    declaration = "bool cancelPrompt();"
    if head.count(declaration) != 1 or "v08ProcessPrompt" in head:
        raise ValueError("Native prompt header composition differs")
    head = head.replace(
        declaration,
        """bool cancelPrompt(const SPELLipcMessage* ownerReply = nullptr);
        void v08ProcessPrompt(const SPELLipcMessage& msg);
        std::string m_v08PromptId;
        std::string m_v08PromptOutcome = "UNKNOWN";
        bool m_v08PromptUncertain = false;""",
    )
    replace(
        '#include "/candidate/mutation_gate.H"',
        '#include "/candidate/mutation_gate.H"\n#include "/candidate/prompt_gate.H"',
    )
    replace(
        "void SPELLserverCif::processMessage( const SPELLipcMessage& msg )\n{\n",
        """void SPELLserverCif::processMessage( const SPELLipcMessage& msg )
{
    // Private prompt-enabled build only. The default native image keeps the
    // original deny policy. Other native mutations remain closed.
    if (msg.getId() == "MSG_ANSWER" || msg.getId() == "MSG_CANCEL") {
        v08ProcessPrompt(msg);
        return;
    }
""",
    )
    # No new native thread is created. ANSWER remains ordered on the original
    # reader; CANCEL retains the original asynchronous dispatcher and scheduler.
    replace(
        "// One CIF belongs to the process-wide executor.",
        """void SPELLserverCif::v08ProcessPrompt(const SPELLipcMessage& msg)
{
    if (!v08_prompt_reply_valid(msg.getId(), msg.getType() == MSG_TYPE_ONEWAY,
                                msg.v08Fields(), getProcId())) {
        v08_note_disabled_mutation(getProcId(), msg.getId());
        return;
    }
    try {
        if (msg.getId() == "MSG_CANCEL") {
            if (!cancelPrompt(&msg))
                v08_note_disabled_mutation(getProcId(), msg.getId());
            return;
        }
        {
            std::lock_guard<std::mutex> response(m_promptAnswerLock);
            if (m_v08PromptUncertain || !m_promptPending || !m_promptAnswer.isVoid()
                || m_v08PromptId.empty() || msg.get("V08PromptId") != m_v08PromptId)
                throw std::runtime_error("Native prompt generation no longer pending");
        }
        // Context checks the original worker, actual prompt, answer digest and
        // live owner. Release the mailbox during RPC so timeout/ACK can proceed.
        v08_consume_prompt(getProcId(), msg);
        {
            std::lock_guard<std::mutex> response(m_promptAnswerLock);
            if (m_v08PromptUncertain || !m_promptPending || !m_promptAnswer.isVoid()
                || msg.get("V08PromptId") != m_v08PromptId)
                throw std::runtime_error("Native prompt changed during authorization");
            m_promptAnswer = msg;
            m_v08PromptOutcome = "ANSWER_SELECTED";
            m_promptAnswerReady.notify_all();
        }
    } catch (const std::exception&) {
        v08_note_disabled_mutation(getProcId(), msg.getId());
    }
}

// One CIF belongs to the process-wide executor.""",
    )
    replace(
        """        m_promptAnswer = VOID_MESSAGE;
        m_promptPending = true;
    }
    // Status publication""",
        """        if (m_v08PromptUncertain || !m_v08PromptId.empty())
            THROW_EXCEPTION("Native prompt fenced", "Previous prompt outcome is unproved", SPELL_ERROR_EXECUTION);
        // Entropy failure must not publish an unidentifiable pending prompt.
        // Refuse the generation before arming; do not retry inside native code.
        try {
            m_v08PromptId = v08_new_prompt_id();
        } catch (const std::exception&) {
            m_v08PromptUncertain = true;
            THROW_EXCEPTION("Native prompt fenced", "Prompt identity unavailable", SPELL_ERROR_EXECUTION);
        }
        m_promptAnswer = VOID_MESSAGE;
        m_promptPending = true;
        m_v08PromptOutcome = "UNKNOWN";
    }
    try {
        SPELLsafeThreadOperations ops("SPELLserverCif::prompt registration");
        v08_declare_prompt(getProcId(), m_v08PromptId, m_promptMessage);
    } catch (const std::exception&) {
        std::lock_guard<std::mutex> response(m_promptAnswerLock);
        m_promptPending = false;
        m_v08PromptUncertain = true;
        THROW_EXCEPTION("Native prompt fenced", "Prompt registration unproved", SPELL_ERROR_EXECUTION);
    }
    m_promptMessage.set("V08PromptId", m_v08PromptId);
    // Status publication""",
    )
    replace(
        "bool SPELLserverCif::cancelPrompt()",
        "bool SPELLserverCif::cancelPrompt(const SPELLipcMessage* ownerReply)",
    )
    replace(
        """    std::lock_guard<std::mutex> transition(spellPromptTransitionLock);
    SPELLipcMessage promptEnd;
""",
        """    std::lock_guard<std::mutex> transition(spellPromptTransitionLock);
    if (ownerReply) {
        {
            std::lock_guard<std::mutex> response(m_promptAnswerLock);
            if (m_v08PromptUncertain || !m_promptPending || !m_promptAnswer.isVoid()
                || m_v08PromptId.empty() || ownerReply->get("V08PromptId") != m_v08PromptId)
                return false;
        }
        // This is the original asynchronous CANCEL worker, not the ACK reader.
        // The transition lock preserves scheduler startup ordering; the answer
        // mutex is released so timeout/answer selection may safely beat this RPC.
        v08_consume_prompt(getProcId(), *ownerReply);
    }
    SPELLipcMessage promptEnd;
""",
    )
    replace(
        """        if (!m_promptPending || !m_promptAnswer.isVoid()) return false;
        // Claim cancellation""",
        """        if (!m_promptPending || !m_promptAnswer.isVoid()) return false;
        if (ownerReply && (m_v08PromptUncertain ||
                ownerReply->get("V08PromptId") != m_v08PromptId)) return false;
        m_v08PromptOutcome = ownerReply ? "CANCEL_SELECTED" : "UNKNOWN";
        // Claim cancellation""",
    )
    replace(
        """            // Use the same native option conversion as an explicit answer.
            m_promptAnswer = SPELLipcMessage(MessageId::MSG_ID_PROMPT_ANSWER);""",
        """            // The native default, not an external reply, won this generation.
            m_v08PromptOutcome = "TIMEOUT";
            // Use the same native option conversion as an explicit answer.
            m_promptAnswer = SPELLipcMessage(MessageId::MSG_ID_PROMPT_ANSWER);""",
    )
    replace(
        """    const bool cancelled = m_promptAnswer.getId() == MessageId::MSG_ID_CANCEL;
    SPELLipcMessage promptEnd(m_promptMessage);""",
        """    const bool cancelled = m_promptAnswer.getId() == MessageId::MSG_ID_CANCEL;
    const std::string v08PromptId = m_v08PromptId;
    const std::string v08Outcome = m_v08PromptOutcome;
    SPELLipcMessage promptEnd(m_promptMessage);""",
    )
    replace(
        """        SPELLexecutor::instance().getScheduler().finishPrompt();
    }
}""",
        """        SPELLexecutor::instance().getScheduler().finishPrompt();
    }
    try {
        v08_close_prompt(getProcId(), v08PromptId, v08Outcome);
    } catch (const std::exception&) {
        std::lock_guard<std::mutex> guard(m_promptAnswerLock);
        m_v08PromptUncertain = true;
        THROW_EXCEPTION("Native prompt fenced", "Prompt outcome report unproved", SPELL_ERROR_EXECUTION);
    }
    {
        std::lock_guard<std::mutex> guard(m_promptAnswerLock);
        if (m_v08PromptId != v08PromptId)
            THROW_EXCEPTION("Native prompt fenced", "Prompt generation changed", SPELL_ERROR_EXECUTION);
        m_v08PromptId.clear();
    }
}""",
    )
    # Validate all expected anchors before modifying either original source file.
    header.write_text(head)
    unit.write_text(text)
