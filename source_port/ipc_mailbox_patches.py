"""Protect response queue lifetime through publication; diagnostic overlay only.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib

SOURCE = 'lib/SPELL_IPC/src/SPELLipcMessageMailbox.C'
PREIMAGE = 'f5f7c43ee5206bdb4cfa8c95676cbfa98c96130231095b62e968fc9220c82595'


def apply(content):
    if hashlib.sha256(content).hexdigest() != PREIMAGE:
        raise ValueError('Unexpected IPC mailbox preimage')
    text = content.decode('utf-8')
    def body(signature, replacement):
        nonlocal text
        start = text.index(signature)
        opening = text.index('{', start)
        ending = text.index('\n}', opening) + 2
        text = text[:opening] + replacement + text[ending:]
    body('void SPELLipcMessageMailbox::cancel( std::string id )', '''{
    SPELLmonitor monitor(m_lock);
    SPELLipcMessageQueueMap::iterator entry = m_queueMap.find(id);
    if (entry == m_queueMap.end()) return;
    SPELLipcMessageQueue* queue = entry->second;
    // A response already queued wins. Never wait on a full queue while holding
    // the map lock: retrieve must acquire that lock before it can pull.
    if (!queue->isEmpty()) return;
    SPELLipcMessage response(MessageId::MSG_ID_CANCEL);
    response.setType(MSG_TYPE_RESPONSE);
    queue->push(response);
}''')
    body('bool SPELLipcMessageMailbox::place( std::string id, const SPELLipcMessage& msg )', '''{
    // remove() takes the same lock. Keep the queue alive until push has fully
    // returned, including its final mutex unlock after waking the consumer.
    SPELLmonitor monitor(m_lock);
    SPELLipcMessageQueueMap::iterator entry = m_queueMap.find(id);
    if (entry == m_queueMap.end()) return false;
    SPELLipcMessageQueue* queue = entry->second;
    // First response wins; duplicate replies must not block a waiting reader.
    if (!queue->isEmpty()) return false;
    queue->push(msg);
    return true;
}''')
    return text.encode('utf-8')
