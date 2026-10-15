"""Preserve prompt answer arrival order and wake prompts on explicit abort.

SPDX-License-Identifier: GPL-3.0-or-later
Apply after the timed-default correction; retain all original source notices.
"""
import hashlib

PREIMAGES = {
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
    if name.endswith('SPELLserverCif.C'):
        before = '''    if (msgId == ExecutorMessages::MSG_CMD_ABORT)
    {
        high_priority = true;
    }'''
        after = '''    if (msgId == ExecutorMessages::MSG_CMD_ABORT)
    {
        // A prompt waits on its own answer condition, not the scheduler's
        // normal wait event. Release it before queuing the explicit abort.
        // cancelPrompt() is a no-op when no unanswered prompt is pending.
        cancelPrompt();
        high_priority = true;
    }'''
    else:
        kind = 'Client' if name.endswith('SPELLipcClientInterface.C') else 'Server'
        start = text.index(f'void SPELLipc{kind}Interface::incomingMessage(')
        end = text.index('\n}', start)
        method = text[start:end]
        anchor = ('    std::string msgId = msg.requestId();' if kind == 'Client'
                  else '    //DEBUG(NAME + "Creating message processor");')
        if method.count(anchor) != 1:
            raise ValueError('Prompt control dispatch anchor differs: ' + name)
        before, after = method, method.replace(anchor, ORDERED + anchor)
    if text.count(before) != 1:
        raise ValueError('Prompt control anchor differs: ' + name)
    return text.replace(before, after).encode('utf-8')
