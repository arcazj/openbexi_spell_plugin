"""Preserve prompt answer arrival order and wake prompts on explicit abort.

SPDX-License-Identifier: GPL-3.0-or-later
Apply after the timed-default correction; retain all original source notices.
"""
import hashlib

PREIMAGES = {
    'include/SPELL_CIFS/SPELLserverCif.H': (
        'ad3ce9638c238300604e0408cacfa387a561cf0c9c662583b6bcccee5fffdeba',
        '6bd06b476bab0f7007315bd5aef68745e690ec9e28cd6d8c432d43d144a2c1f4'),
    'lib/SPELL_IPC/src/SPELLipcClientInterface.C': (
        '2a2cfe1befef43d44229e1438e7cd5925aa0699a8c2d18b501376b980e9334a5',
        '454121f636ce13dfb469bc4912dd62a2267b16dc5547610e362240b173f84f8a'),
    'lib/SPELL_IPC/src/SPELLipcServerInterface.C': (
        '9712a92efe49d1bc3b02281606e8ef36d336b5cbe54fc33e9c4a414022a893b5',
        '6c1f71a937499f041010b6cdcf395b7d95c16db0321985488c018ffca99d171f'),
    'lib/SPELL_CIFS/src/SPELLserverCif.C': (
        '9d37476b9f14a41945f2a5afee1e5b6d3f659bd3fd8236aff4f0d2a2106005a7',
        'af2c86036aee031acc63802d778d5f058419b7fbc3a75e6006cfa5faea132aaa'),
}

ORDERED = '''    // Prompt answers only forward a one-way message or signal the prompt
    // waiter. Dispatch them on this channel's receive thread so independently
    // scheduled workers cannot make a later answer win the pending prompt.
    // Ordinary messages and requests retain their asynchronous processing.
    if (msg.getType() == MSG_TYPE_ONEWAY
        && msg.getId() == MessageId::MSG_ID_PROMPT_ANSWER)
    {
        m_listener->processMessage(msg);
        return;
    }

'''


def apply(name, original, ported):
    if tuple(hashlib.sha256(value).hexdigest() for value in (original, ported)) != PREIMAGES[name]:
        raise ValueError('Prompt control preimage differs: ' + name)
    text = ported.decode('utf-8')

    def replace(before, after):
        nonlocal text
        if text.count(before) != 1:
            raise ValueError('Prompt control anchor differs: ' + name)
        text = text.replace(before, after)

    if name.endswith('SPELLserverCif.H'):
        replace('void cancelPrompt();', 'bool cancelPrompt();')
    elif name.endswith('SPELLserverCif.C'):
        replace('''    if (msgId == ExecutorMessages::MSG_CMD_ABORT)
    {
        high_priority = true;
    }''', '''    if (msgId == ExecutorMessages::MSG_CMD_ABORT)
    {
        // A pending prompt owns the complete abort transition. Do not dispatch
        // another abort after waking its Python thread.
        if (cancelPrompt()) return;
        high_priority = true;
    }''')
        start = text.index('void SPELLserverCif::cancelPrompt()')
        end = text.index('\n}', start) + 2
        replace(text[start:end], '''bool SPELLserverCif::cancelPrompt()
{
    // Keep the waiter (and spurious wakeups) behind this mutex until the
    // scheduler's abort and Python driver notification have completed. Waking
    // it earlier can invert the executor command mutex and Python GIL.
    std::lock_guard<std::mutex> response(m_promptAnswerLock);
    if (!m_promptPending || !m_promptAnswer.isVoid()) return false;
    m_promptPending = false;
    m_promptAnswer = SPELLipcMessage(MessageId::MSG_ID_CANCEL);
    SPELLipcMessage promptEnd(m_promptMessage);
    m_promptMessage = VOID_MESSAGE;
    promptEnd.setId(MessageId::MSG_ID_PROMPT_END);
    promptEnd.setType(MSG_TYPE_ONEWAY);
    sendGUIMessage(&promptEnd);
    SPELLexecutor::instance().getScheduler().cancelPrompt();
    m_promptAnswerReady.notify_all();
    return true;
}''')
        replace('''        // Abort execution in this case
        SPELLexecutor::instance().abort("Prompt cancelled",true);''',
                '''        // cancelPrompt() completed the abort before releasing this waiter.''')
    else:
        kind = 'Client' if name.endswith('SPELLipcClientInterface.C') else 'Server'
        start = text.index(f'void SPELLipc{kind}Interface::incomingMessage(')
        end = text.index('\n}', start)
        method = text[start:end]
        anchor = ('    std::string msgId = msg.requestId();' if kind == 'Client'
                  else '    //DEBUG(NAME + "Creating message processor");')
        if method.count(anchor) != 1:
            raise ValueError('Prompt control dispatch anchor differs: ' + name)
        replace(method, method.replace(anchor, ORDERED + anchor))
    return text.encode('utf-8')
