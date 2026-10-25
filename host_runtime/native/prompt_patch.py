"""Opt-in hooks for the exact original native prompt synchronization paths.

This patches the reproduced native source AFTER the existing v0.8 admission
patch. No published runtime is modified. Ordinary cohorts keep prompts denied.
"""

# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib

PREIMAGES = {
    "include/SPELL_CIFS/SPELLserverCif.H": "b93acc7e7d8c54f0c8e6825db20fe5fdc91dde01266f24df2f16923d7d10a006",
    "lib/SPELL_CIFS/src/SPELLserverCif.C": "e78bdebd8493e6309380dfbc2bcb39ecd4f9554aeb50cd4089aad87da2ac5bc3",
}


def apply_prompt_boundary(source):
    texts = {}
    for name, expected in PREIMAGES.items():
        content = (source / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Native prompt preimage differs: " + name)
        texts[name] = content.decode()
    header, unit = PREIMAGES

    def replace(name, before, after):
        if texts[name].count(before) != 1:
            raise ValueError("Ambiguous native prompt insertion: " + name)
        texts[name] = texts[name].replace(before, after)

    replace(
        header,
        "bool cancelPrompt();",
        """bool cancelPrompt();
        bool cancelPromptForId(const std::string& expectedPrompt);
        bool v08HandlePromptReply(const SPELLipcMessage& msg);""",
    )
    replace(
        header,
        "bool m_promptPending = false;",
        """bool m_promptPending = false;
        std::string m_v08PromptId;
        std::string m_v08PromptOutcome = "UNKNOWN";""",
    )
    replace(
        unit,
        '#include "/candidate/mutation_gate.H"',
        '#include "/candidate/mutation_gate.H"\n#include "/candidate/prompt_gate.H"',
    )
    entry = "void SPELLserverCif::processMessage( const SPELLipcMessage& msg )\n{\n"
    replace(
        unit,
        entry,
        entry
        + """    if (v08_prompt_enabled() &&
        (msg.getId() == "MSG_ANSWER" || msg.getId() == "MSG_CANCEL")) {
        try {
            if (v08HandlePromptReply(msg)) return;
        } catch (...) { }
        v08_note_disabled_mutation(getProcId(), msg.getId());
        return;
    }
""",
    )
    # Open while the existing transition lock excludes cancellation, but NEVER
    # hold the answer lock/GIL across authorization or original GUI ACK waits.
    replace(
        unit,
        """    // Status publication waits for an acknowledgement on the same receive
""",
        """    if (v08_prompt_enabled()) {
        try {
            const std::string identity = v08_prompt_identity();
            {
                std::lock_guard<std::mutex> response(m_promptAnswerLock);
                m_v08PromptId = identity;
                m_v08PromptOutcome = "UNKNOWN";
            }
            m_promptMessage.set("V08PromptId", identity);
            const nlohmann::json definition = {
                {"fields", m_promptMessage.v08Fields()},
                {"default_provided", m_promptDef.defaultProvided},
                {"timeout_seconds", m_promptDef.timeout.getSeconds()},
                {"timeout_milliseconds", m_promptDef.timeout.getMilliseconds()},
                {"timeout_microseconds", m_promptDef.timeout.getMicroseconds()}
            };
            SPELLsafeThreadOperations ops("v08 prompt registration");
            v08_open_prompt(getProcId(), identity, definition);
        } catch (...) {
            {
                std::lock_guard<std::mutex> response(m_promptAnswerLock);
                m_promptPending = false;
            }
            THROW_EXCEPTION("Native prompt denied", "Prompt registration unavailable", SPELL_ERROR_PROCESS);
        }
    }
    // Status publication waits for an acknowledgement on the same receive
""",
    )
    replace(
        unit,
        "bool SPELLserverCif::cancelPrompt()\n{\n",
        """bool SPELLserverCif::cancelPrompt()
{
    return cancelPromptForId("");
}

bool SPELLserverCif::cancelPromptForId(const std::string& expectedPrompt)
{
""",
    )
    replace(
        unit,
        """        if (!m_promptPending || !m_promptAnswer.isVoid()) return false;
        // Claim cancellation""",
        """        if (!m_promptPending || !m_promptAnswer.isVoid()) return false;
        if (!expectedPrompt.empty() && expectedPrompt != m_v08PromptId) return false;
        m_v08PromptOutcome = expectedPrompt.empty() ? "UNKNOWN" : "CANCEL_SELECTED";
        // Claim cancellation""",
    )
    replace(
        unit,
        """            // Use the same native option conversion as an explicit answer.
""",
        """            m_v08PromptOutcome = "DEFAULT_SELECTED";
            // Use the same native option conversion as an explicit answer.
""",
    )
    replace(
        unit,
        """    SPELLipcMessage promptEnd(m_promptMessage);
    m_promptMessage = VOID_MESSAGE;
    response.unlock();
    // Cancellation already owns its end notification""",
        """    SPELLipcMessage promptEnd(m_promptMessage);
    m_promptMessage = VOID_MESSAGE;
    const std::string v08Identity = m_v08PromptId;
    const std::string v08Outcome = m_v08PromptOutcome;
    m_v08PromptId.clear();
    response.unlock();
    if (v08_prompt_enabled()) v08_close_prompt(getProcId(), v08Identity, v08Outcome);
    // Cancellation already owns its end notification""",
    )
    # This method is entered on the original ordered answer receive path.
    # Authorization never waits for an original native ACK or Python/GIL work.
    # A timeout/cancel may win while RPC is in progress: recheck under the same
    # native mailbox mutex before selecting any answer or waking the waiter.
    handler = """
bool SPELLserverCif::v08HandlePromptReply(const SPELLipcMessage& msg)
{
    std::string prompt;
    {
        std::lock_guard<std::mutex> response(m_promptAnswerLock);
        if (!m_promptPending || !m_promptAnswer.isVoid()
            || m_v08PromptId.empty() || msg.get("V08PromptId") != m_v08PromptId)
            return false;
        prompt = m_v08PromptId;
    }
    v08_consume_prompt(getProcId(), prompt, msg);
    if (msg.getId() == "MSG_CANCEL") return cancelPromptForId(prompt);
    {
        std::lock_guard<std::mutex> response(m_promptAnswerLock);
        if (!m_promptPending || !m_promptAnswer.isVoid() || m_v08PromptId != prompt)
            return false;
        m_v08PromptOutcome = "ANSWER_SELECTED";
        m_promptAnswer = msg;
        m_promptAnswerReady.notify_all();
    }
    return true;
}

"""
    replace(
        unit,
        "void SPELLserverCif::waitPromptAnswer()\n",
        handler + "void SPELLserverCif::waitPromptAnswer()\n",
    )
    for name, text in texts.items():
        (source / name).write_text(text)
