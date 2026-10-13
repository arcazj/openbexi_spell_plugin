"""Checked fix for missing-scope error replies in original native context.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib

NAME = 'lib/SPELL_CTX/src/SPELLcontext.C'
UPSTREAM_SHA256 = 'cf4576a8a95c543cddd53b8cb4f136a53e0114c1fc5bf3ebd6e39b1c0ff9129c'
PORTED_SHA256 = 'e390d60cff2a8a92f5cb7a684ef0ca95965c228b7d38566c8dddcadf0207aa4a'


def apply(original, ported):
    assert hashlib.sha256(original).hexdigest() == UPSTREAM_SHA256
    assert hashlib.sha256(ported).hexdigest() == PORTED_SHA256
    text = ported.decode('utf-8')
    old = '''\t\tm_sharedData.clearScope(scope);
\t\tresult = "True";
\t\tnotifySharedDataOperation( msg, CLEAR_SHARED_SCOPE, "", "", scope );'''
    new = '''        // An absent scope is a normal failed operation. Always return an
        // IPC error response so the executor and its controller remain usable.
        try
        {
            m_sharedData.clearScope(scope);
            result = "True";
            notifySharedDataOperation( msg, CLEAR_SHARED_SCOPE, "", "", scope );
        }
        catch(SPELLcoreException& ex)
        {
            errors = ex.what() + "\\n";
            result = "False";
        }'''
    assert text.count(old) == 1
    return text.replace(old, new).encode('utf-8')
