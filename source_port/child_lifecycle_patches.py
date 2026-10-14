"""Preimage-checked child close/kill identity and native confirmation handling.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib

PREIMAGES = {
    'lib/SPELL_EXC/src/SPELLchildManager.C': (
        'd026e3b74f02cf5a588c44e3e6d1012f378feabb0300b657ca5167c8b2bb6169',
        'b775fac05feb16f6ec775322c693eeef4ce6b3111aba2b20d560f1192b92182d'),
    'lib/SPELL_CIFS/src/SPELLserverCif.C': (
        '9d37476b9f14a41945f2a5afee1e5b6d3f659bd3fd8236aff4f0d2a2106005a7',
        '46e57ce597b42ca80c2d4f27ec065aaf2d676ad55d8f9b5fcb7ba07c04f7fe82'),
    'lib/SPELL_CTX/src/SPELLexecutor.C': (
        '63db5c0e063e08ad4fea0bcd4c66efb53b205beb6218a226c6ab7573ae677d32',
        '59809d4d3d333207b5d3def831b6e8572d3ad20a1cd36298baa18ed7893ccee2'),
}


def apply(name, original, ported):
    if tuple(hashlib.sha256(value).hexdigest() for value in (original, ported)) != PREIMAGES[name]:
        raise ValueError('Child lifecycle preimage differs: '+name)
    text = ported.decode('utf-8')
    if name.endswith('SPELLchildManager.C'):
        for action in ('close', 'kill'):
            before = '''void SPELLchildManager::%sChildProcedure()
{
    SPELLmonitor m(m_lock);
    reset();
    SPELLserverCif& cif = dynamic_cast<SPELLserverCif&>(SPELLexecutor::instance().getCIF());
    cif.%sSubprocedure( m_childProc );
}''' % (action, action)
            after = '''void SPELLchildManager::%sChildProcedure()
{
    std::string child;
    {
        SPELLmonitor lock(m_lock);
        child = m_childProc;
    }
    // A failed launch has no child. Preserve the wrapper's cancel/skip policy.
    if (child.empty()) return;
    // Native close notifications may arrive before the request's reply.
    // They must not wait for a child-manager lock held by this request.
    SPELLserverCif& cif = dynamic_cast<SPELLserverCif&>(SPELLexecutor::instance().getCIF());
    cif.%sSubprocedure(child);
    {
        SPELLmonitor lock(m_lock);
        // A rejected or uncertain request retains the last known child state.
        // Another caller's new child must never be reset by this completion.
        if (m_childProc == child) reset();
    }
}''' % (action, action)
            if text.count(before) != 1:
                raise ValueError('Child lifecycle block differs: '+action)
            text = text.replace(before, after)
    elif name.endswith('SPELLserverCif.C'):
        for action in ('Close', 'Kill'):
            start = text.index('void SPELLserverCif::specific'+action+'Subprocedure(')
            end = text.index('\n}', start)+2
            block = text[start:end]
            before = 'MessageField::FIELD_SPROC_ID, procId'
            if block.count(before) != 1:
                raise ValueError('Child context request target differs')
            block = block.replace(before, 'MessageField::FIELD_PROC_ID, procId')
            before = '    sendCTXRequest( '+action.lower()+'Msg, m_ipcTimeoutCtxRequestMsec );'
            if block.count(before) != 1:
                raise ValueError('Child context response anchor differs')
            block = block.replace(before, '''    SPELLipcMessage response = sendCTXRequest(%sMsg, m_ipcTimeoutCtxRequestMsec);
    if (response.isVoid() || response.getType() != MSG_TYPE_RESPONSE
        || response.getId() != ContextMessages::RSP_%s_EXEC)
    {
        std::string reason = response.get(MessageField::FIELD_ERROR) + ": "
            + response.get(MessageField::FIELD_REASON);
        if (reason == ": ") reason = "Context did not confirm child termination";
        THROW_EXCEPTION("Unable to %s subprocedure", reason, SPELL_ERROR_EXECUTION);
    }''' % (action.lower(), action.upper(), action.lower()))
            text = text[:start]+block+text[end:]
    else:
        before = '''    else if ( requestId == ContextMessages::REQ_INSTANCE_ID )
    {
        response = SPELLcontext::instance().getInstanceId( msg );
    }'''
        after = '''    else if (requestId == ContextMessages::REQ_CLOSE_EXEC
             || requestId == ContextMessages::REQ_KILL_EXEC)
    {
        const bool close = requestId == ContextMessages::REQ_CLOSE_EXEC;
        const std::string replyId = close ? ContextMessages::RSP_CLOSE_EXEC
                                          : ContextMessages::RSP_KILL_EXEC;
        try
        {
            const std::string parent = m_model.getInstanceId();
            const std::string target = msg.get(MessageField::FIELD_PROC_ID);
            if (msg.getType() != MSG_TYPE_REQUEST || msg.getReceiver() != "CTX"
                || msg.getSender() != parent || target.empty() || target == parent)
                THROW_EXCEPTION("Child lifecycle request rejected", "Invalid parent or child identity", SPELL_ERROR_EXECUTION);
            SPELLexecutor* child = SPELLexecutorManager::instance().getExecutor(target);
            // getExecutor also resolves service aliases; require the exact
            // open instance and its immediate parent before any lifecycle work.
            if (child->getModel().getInstanceId() != target
                || child->getParentInstanceId() != parent)
                THROW_EXCEPTION("Child lifecycle request rejected", "Target is not an immediate child: " + target, SPELL_ERROR_EXECUTION);
            // A synchronous GUI round trip holds the context's client mutex
            // while waiting. Re-entering that context from the GUI deadlocks.
            // The context owns lifecycle changes and publishes the original
            // one-way GUI/parent operation notifications after completion.
            response = close ? SPELLcontext::instance().closeExecutor(msg)
                             : SPELLcontext::instance().killExecutor(msg);
        }
        catch (SPELLcoreException& error)
        {
            response = SPELLipcHelper::createErrorResponse(replyId, msg);
            response.set(MessageField::FIELD_ERROR, "Child lifecycle request rejected");
            response.set(MessageField::FIELD_REASON,
                "Target " + msg.get(MessageField::FIELD_PROC_ID) + ": " + error.what());
        }
    }
''' + before
        if text.count(before) != 1:
            raise ValueError('Context child lifecycle dispatch anchor differs')
        text = text.replace(before, after)
    return text.encode('utf-8')
