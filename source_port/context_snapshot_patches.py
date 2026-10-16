"""Protect native listener context metadata with coherent state snapshots.

SPDX-License-Identifier: GPL-3.0-or-later
No IPC call, process wait, or event delivery runs under the state mutex.
"""
import hashlib

SOURCE = 'lib/SPELL_LST/src/SPELLlistenerContext.C'
ORIGINAL = 'ce7c6b3e16847584ad0a6e0e677ed5f9c16de4b560c3a29f7b08f1e8d72c1e2f'
PORTED = 'aac1c7e223a52622670a836464d55e6ad54b7f96fd1250ab4f755867c012d5ac'
GUARD = 'std::lock_guard<std::mutex> stateLock(spellListenerContextState);'


def apply(name, original, ported):
    if (name != SOURCE or hashlib.sha256(original).hexdigest() != ORIGINAL
            or hashlib.sha256(ported).hexdigest() != PORTED):
        raise ValueError('Unexpected listener context snapshot preimage')
    text = ported.decode('utf-8')

    def method(signature, transform):
        nonlocal text
        start = text.index(signature)
        end = text.index('//=============================================================================', start)
        text = text[:start] + transform(text[start:end]) + text[end:]

    def replace(text, before, after):
        assert text.count(before) == 1, before
        return text.replace(before, after)

    def shutdown(block):
        block = block.replace('m_openContexts', 'contexts')
        marker = '    std::map<std::string, ContextInfo>::iterator it;'
        return replace(block, marker, '    std::map<std::string, ContextInfo> contexts;\n'
            '    { ' + GUARD + ' contexts = m_openContexts; }\n' + marker)

    method('int SPELLlistenerContext::shutdown()', shutdown)
    method('SPELLipcMessage SPELLlistenerContext::destroyContext(', lambda block: replace(block,
        '    ContextInfo& ctxInfo = m_openContexts[name];\n    ctxInfo.m_status = MessageValue::DATA_CTX_AVAILABLE;',
        '    ContextInfo ctxInfo;\n    {\n        ' + GUARD + '\n'
        '        ContextInfo& current = m_openContexts[name];\n'
        '        current.m_status = MessageValue::DATA_CTX_AVAILABLE;\n'
        '        ctxInfo = current;\n    }'))

    def stop(block):
        block = replace(block, '    ContextInfo* ctxInfo;', '    ContextInfo ctxInfo;')
        block = replace(block, '    ctxInfo = &m_openContexts[name];',
            '    { ' + GUARD + ' ctxInfo = m_openContexts[name]; }')
        block = replace(block,
            '    \t    ctxInfo = &m_openContexts[msg.get(MessageField::FIELD_CTX_NAME)];\n'
            '    \t    ctxInfo->m_status = MessageValue::DATA_CTX_AVAILABLE;',
            '            {\n                ' + GUARD + '\n'
            '                ContextInfo& current = m_openContexts[msg.get(MessageField::FIELD_CTX_NAME)];\n'
            '                current.m_status = MessageValue::DATA_CTX_AVAILABLE;\n'
            '                ctxInfo = current;\n            }')
        return block.replace('ctxInfo->', 'ctxInfo.')

    method('SPELLipcMessage SPELLlistenerContext::stopContext(', stop)

    def opened(block):
        block = replace(block, '    ContextInfo* ctxInfo;', '    ContextInfo ctxInfo;')
        block = replace(block,
            '    ctxInfo = &m_openContexts[ctxName];\n'
            '    ctxInfo->m_key = msg.getKey();\n'
            '    ctxInfo->m_port = STRI(msg.get(MessageField::FIELD_CTX_PORT));\n'
            '    ctxInfo->m_status = MessageValue::DATA_CTX_RUNNING;',
            '    {\n        ' + GUARD + '\n'
            '        ContextInfo& current = m_openContexts[ctxName];\n'
            '        current.m_key = msg.getKey();\n'
            '        current.m_port = STRI(msg.get(MessageField::FIELD_CTX_PORT));\n'
            '        current.m_status = MessageValue::DATA_CTX_RUNNING;\n'
            '        ctxInfo = current;\n    }')
        return block.replace('ctxInfo->', 'ctxInfo.')

    method('void SPELLlistenerContext::onNewContext(', opened)
    method('void SPELLlistenerContext::fillContextInfo(', lambda block: replace(block, '\n{\n',
        '\n{\n    ' + GUARD + '\n'))

    def process(block, failed):
        block = replace(block, '    ContextInfo* ctxInfo;', '    ContextInfo ctxInfo;')
        key = 'identifier.substr(4)' if failed else 'ctxName'
        status = 'ERROR' if failed else 'KILLED'
        block = replace(block,
            '    ctxInfo = &m_openContexts[' + key + '];\n'
            '    ctxInfo->m_status = MessageValue::DATA_CTX_' + status + ';',
            '    {\n        ' + GUARD + '\n'
            '        ContextInfo& current = m_openContexts[' + key + '];\n'
            '        current.m_status = MessageValue::DATA_CTX_' + status + ';\n'
            '        ctxInfo = current;\n    }')
        return block.replace('ctxInfo->', 'ctxInfo.')

    method('void SPELLlistenerContext::processKilled(', lambda block: process(block, False))
    method('void SPELLlistenerContext::processFailed(', lambda block: process(block, True))
    # A translation-unit mutex preserves the installed class ABI. Each listener
    # process owns one context registry; snapshots are copied before any IPC.
    prefix = '#include <mutex>\nstatic std::mutex spellListenerContextState;\n\n'
    return (prefix + text).encode('utf-8')
