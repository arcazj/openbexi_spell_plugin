"""Keep ordered answer reception free of prompt transition and IPC waits.

SPDX-License-Identifier: GPL-3.0-or-later
Apply after prompt_control_patches; preserve the native class layout.
"""
import hashlib

SOURCE = 'lib/SPELL_CIFS/src/SPELLserverCif.C'
PREIMAGES = {SOURCE: (
    '9d37476b9f14a41945f2a5afee1e5b6d3f659bd3fd8236aff4f0d2a2106005a7',
    '383b113b7e2e568bea153c94ec23d4cf33c9a503677d8960647fc094a1446c6d')}


def apply(name, original, ported):
    if tuple(hashlib.sha256(value).hexdigest() for value in (original, ported)) != PREIMAGES.get(name):
        raise ValueError('Prompt startup preimage differs: ' + name)
    text = ported.decode('utf-8')

    def replace(before, after):
        nonlocal text
        if text.count(before) != 1:
            raise ValueError('Prompt startup anchor differs: ' + before)
        text = text.replace(before, after)

    replace('void SPELLserverCif::startPrompt()\n{', '''// One CIF belongs to the process-wide executor. Keep this transition mutex
// separate from the answer mailbox and preserve the original class ABI.
static std::mutex spellPromptTransitionLock;

void SPELLserverCif::startPrompt()
{''')
    replace('''    // Publish a fully initialized wait before the client can answer.
    std::lock_guard<std::mutex> response(m_promptAnswerLock);
    m_promptAnswer = VOID_MESSAGE;
    m_promptPending = true;''', '''    // Cancellation must follow complete scheduler startup. Release the GIL
    // while acquiring this mutex: a preceding cancellation can need Python.
    std::unique_lock<std::mutex> transition(spellPromptTransitionLock, std::defer_lock);
    {
        SPELLsafeThreadOperations ops("SPELLserverCif::startPrompt transition");
        transition.lock();
    }
    {
        std::lock_guard<std::mutex> response(m_promptAnswerLock);
        m_promptAnswer = VOID_MESSAGE;
        m_promptPending = true;
    }
    // Status publication waits for an acknowledgement on the same receive
    // channel as ordered answers. Never hold the answer mutex across it.''')
    start = text.index('bool SPELLserverCif::cancelPrompt()')
    end = text.index('\n}', start) + 2
    replace(text[start:end], '''bool SPELLserverCif::cancelPrompt()
{
    SPELLsafeThreadOperations ops("SPELLserverCif::cancelPrompt transition");
    std::lock_guard<std::mutex> transition(spellPromptTransitionLock);
    SPELLipcMessage promptEnd;
    {
        std::lock_guard<std::mutex> response(m_promptAnswerLock);
        if (!m_promptPending || !m_promptAnswer.isVoid()) return false;
        // Claim cancellation before releasing the mailbox. Answers arriving
        // during abort cannot replace it or block the acknowledgement reader.
        m_promptAnswer = SPELLipcMessage(MessageId::MSG_ID_CANCEL);
        promptEnd = m_promptMessage;
        m_promptMessage = VOID_MESSAGE;
    }
    promptEnd.setId(MessageId::MSG_ID_PROMPT_END);
    promptEnd.setType(MSG_TYPE_ONEWAY);
    sendGUIMessage(&promptEnd);
    SPELLexecutor::instance().getScheduler().cancelPrompt();
    {
        std::lock_guard<std::mutex> response(m_promptAnswerLock);
        // The Python waiter may resume only after the abort transition ends.
        m_promptPending = false;
    }
    m_promptAnswerReady.notify_all();
    return true;
}''')
    replace('auto answered = [this]() { return !m_promptAnswer.isVoid(); };', '''auto answered = [this]() {
        return !m_promptAnswer.isVoid()
            && (m_promptAnswer.getId() != MessageId::MSG_ID_CANCEL || !m_promptPending);
    };''')
    replace('''        if (!m_promptAnswerReady.wait_until(response, deadline, answered))
        {
            // Use the same native option conversion as an explicit answer.''', '''        if (!m_promptAnswerReady.wait_until(response, deadline, answered)
            && m_promptAnswer.isVoid())
        {
            // Use the same native option conversion as an explicit answer.''')
    replace('''    // Late or duplicate answers cannot replace the selected result.
    m_promptPending = false;''', '''    // A deadline cannot overwrite cancellation or wake Python during abort.
    m_promptAnswerReady.wait(response, answered);
    // Late or duplicate answers cannot replace the selected result.
    m_promptPending = false;''')
    return text.encode('utf-8')
