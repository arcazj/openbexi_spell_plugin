"""Native timed defaults with one synchronized winner among answer and cancellation.

SPDX-License-Identifier: GPL-3.0-or-later
Apply after the child lifecycle correction; retain the original source notices.
"""
import hashlib

PREIMAGES = {
    'include/SPELL_CIFS/SPELLserverCif.H': (
        'ad3ce9638c238300604e0408cacfa387a561cf0c9c662583b6bcccee5fffdeba',
        'ffb8d02b1858c2dc75ce4acb80e27910817b11d03c8db57cbeadd311bf6e1453'),
    'lib/SPELL_CIFS/src/SPELLserverCif.C': (
        '9d37476b9f14a41945f2a5afee1e5b6d3f659bd3fd8236aff4f0d2a2106005a7',
        '4e8c8eb53f20678451d412499e174a578a24b94be1701c5c5787136b2dbb1bf2'),
}


def apply(name, original, ported):
    actual = tuple(hashlib.sha256(value).hexdigest() for value in (original, ported))
    if actual != PREIMAGES[name]:
        raise ValueError('Prompt timeout preimage differs: ' + name)
    text = ported.decode('utf-8')

    def replace(before, after):
        nonlocal text
        if text.count(before) != 1:
            raise ValueError('Prompt timeout anchor differs: ' + before)
        text = text.replace(before, after)

    if name.endswith('.H'):
        replace('#define __SPELL_SERVER_CIF_H__',
                '#define __SPELL_SERVER_CIF_H__\n#include <chrono>\n#include <condition_variable>\n#include <mutex>')
        replace('SPELLevent m_promptAnswerEvent;', '''std::mutex m_promptAnswerLock;
        std::condition_variable m_promptAnswerReady;
        bool m_promptPending = false;''')
    else:
        replace('''    	DEBUG("[CIF] Got prompt answer");
    	m_promptAnswer = msg;
    	m_promptAnswerEvent.set();''', '''        std::lock_guard<std::mutex> response(m_promptAnswerLock);
        if (m_promptPending && m_promptAnswer.isVoid())
        {
            m_promptAnswer = msg;
            m_promptAnswerReady.notify_all();
        }''')
        replace('''void SPELLserverCif::startPrompt()
{''', '''void SPELLserverCif::startPrompt()
{
    // Publish a fully initialized wait before the client can answer.
    std::lock_guard<std::mutex> response(m_promptAnswerLock);
    m_promptAnswer = VOID_MESSAGE;
    m_promptPending = true;''')
        replace('''	// Reset the event that will trigger the answer
	m_promptAnswerEvent.clear();
	m_promptAnswer = VOID_MESSAGE;''', '')

        start = text.index('void SPELLserverCif::cancelPrompt()')
        end = text.index('\n}', start) + 2
        text = text[:start] + '''void SPELLserverCif::cancelPrompt()
{
    SPELLipcMessage promptEnd;
    {
        std::lock_guard<std::mutex> response(m_promptAnswerLock);
        if (!m_promptPending || !m_promptAnswer.isVoid()) return;
        m_promptPending = false;
        m_promptAnswer = SPELLipcMessage(MessageId::MSG_ID_CANCEL);
        promptEnd = m_promptMessage;
        m_promptMessage = VOID_MESSAGE;
        m_promptAnswerReady.notify_all();
    }
    promptEnd.setId(MessageId::MSG_ID_PROMPT_END);
    promptEnd.setType(MSG_TYPE_ONEWAY);
    sendGUIMessage(&promptEnd);
    SPELLexecutor::instance().getScheduler().cancelPrompt();
}''' + text[end:]

        start = text.index('void SPELLserverCif::waitPromptAnswer()')
        end = text.index('\n}', start) + 2
        text = text[:start] + '''void SPELLserverCif::waitPromptAnswer()
{
    SPELLsafeThreadOperations ops("SPELLserverCif::waitPromptAnswer()");
    std::unique_lock<std::mutex> response(m_promptAnswerLock);
    auto answered = [this]() { return !m_promptAnswer.isVoid(); };
    const SPELLtime& timeout = m_promptDef.timeout;
    const long double seconds = timeout.getSeconds()
        + timeout.getMilliseconds()/1000.L + timeout.getMicroseconds()/1000000.L;
    if (!m_promptDef.defaultAnswer.empty() && seconds > 0)
    {
        using Clock = std::chrono::steady_clock;
        const auto now = Clock::now();
        const auto requested = std::chrono::duration<long double>(seconds);
        const auto maximum = Clock::time_point::max() - now;
        const auto deadline = requested >= std::chrono::duration<long double>(maximum)
            ? Clock::time_point::max()
            : now + std::chrono::ceil<Clock::duration>(requested);
        if (!m_promptAnswerReady.wait_until(response, deadline, answered))
        {
            // Use the same native option conversion as an explicit answer.
            m_promptAnswer = SPELLipcMessage(MessageId::MSG_ID_PROMPT_ANSWER);
            m_promptAnswer.setType(MSG_TYPE_ONEWAY);
            m_promptAnswer.set(MessageField::FIELD_RVALUE,
                SPELLcifHelper::getRawAnswer(m_promptDef.defaultAnswer, m_promptDef));
        }
    }
    else
    {
        m_promptAnswerReady.wait(response, answered);
    }
    // Late or duplicate answers cannot replace the selected result.
    m_promptPending = false;
    const bool cancelled = m_promptAnswer.getId() == MessageId::MSG_ID_CANCEL;
    SPELLipcMessage promptEnd(m_promptMessage);
    m_promptMessage = VOID_MESSAGE;
    response.unlock();
    // Cancellation already owns its end notification and scheduler transition.
    if (!cancelled)
    {
        promptEnd.setId(MessageId::MSG_ID_PROMPT_END);
        promptEnd.setType(MSG_TYPE_ONEWAY);
        sendGUIMessage(&promptEnd);
        SPELLexecutor::instance().getScheduler().finishPrompt();
    }
}''' + text[end:]
        if 'm_promptAnswerEvent' in text:
            raise ValueError('Unconverted prompt event access')
    return text.encode('utf-8')
