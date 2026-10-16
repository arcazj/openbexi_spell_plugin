"""Prevent a pending timer callback from observing an interrupted condition.

SPDX-License-Identifier: GPL-3.0-or-later
Keep the original class ABI; serialize callbacks with the existing check mutex.
"""
import hashlib

SOURCE='lib/SPELL_EXC/src/SPELLscheduler.C'
PREIMAGES={SOURCE:(
    '2d00d9b9d5e5296799582e7937873639ca4400eb204fec174317b29c36bdd50a',
    '9669db2983f8927c60fbe853a2eae865f15f0a5d8432e9d1c9f1edd6d80ee93b')}


def apply(name,original,ported):
    if tuple(hashlib.sha256(value).hexdigest() for value in (original,ported))!=PREIMAGES.get(name):
        raise ValueError('Wait interruption preimage differs: '+name)
    text=ported.decode('utf-8')
    signature='bool SPELLscheduler::timerCallback( unsigned long elapsed )\n'
    begin=text.index(signature)
    end=text.index('//=============================================================================',begin)
    old=text[begin:end]
    switch=old[old.index('\t\t\t// Depending on the condition type'):old.index('\t\t\tm_checkLock.unlock();')]
    progress=old[old.index('        // Periodic notifications'):old.index('\n    if (abortCheck)')]
    assert progress.endswith('    }')
    progress=progress[:-5]
    replacement=signature+'''{
    // stop() pauses SPELLtimer after its callback. A callback already pending
    // at INTERRUPT must therefore check the controller under the same mutex.
    // Do not block here: startTimer may hold this mutex while joining a timer.
    if (!m_checkLock.trylock()) return false;
    std::unique_lock<SPELLmutex> checkLock(m_checkLock, std::adopt_lock);
    if (m_abortTimer) {
        finishWait(true,false);
        return true;
    }
    if (SPELLexecutor::instance().getController().getStatus()==STATUS_INTERRUPTED)
        return false;
    bool abortCheck = false;
    {
        SPELLsafePythonOperations ops("SPELLscheduler::timerCallback()");
'''+switch+'''    }
'''+progress+'''
    // Keep the same mutex through notifications and completion so INTERRUPT
    // cannot be acknowledged between the condition check and its effects.
    if (abortCheck) finishWait(true,false);
    return abortCheck;
}

'''
    text=text[:begin]+replacement+text[end:]
    index=text.index('#include ')
    text=text[:index]+'#include <mutex>\n'+text[index:]
    return text.encode('utf-8')
