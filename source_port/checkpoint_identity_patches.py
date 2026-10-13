"""Bind original native procedure checkpoints to their real compiled source.

SPDX-License-Identifier: GPL-3.0-or-later
Instance identifiers still name the output checkpoint; source identity uses the
same original procedure-manager resolution as prepareExecution().
"""
import hashlib

SOURCE = 'lib/SPELL_EXC/src/SPELLinterpreter.C'
ORIGINAL = '3dd0a455669237924726637ca4b25ae524acfaf10d577b18a7c36258ad3f1256'
PORTED = '670726c1853be672353f5e35da579d0e1c1569ab457d7c0cfe3d4c29692e3b33'


def apply(name, original, ported):
    assert name == SOURCE
    assert hashlib.sha256(original).hexdigest() == ORIGINAL
    assert hashlib.sha256(ported).hexdigest() == PORTED
    source = ported.decode()
    before = '        startup.procedureFile = m_procedure;'
    after = '''        // An instance id (for example main#1) identifies the executor,
        // not a file. Use precisely the same source resolution as compilation.
        // Persistent/recovery filenames above continue to contain the instance.
        startup.procedureFile = m_config.script ? m_procedure
            : SPELLprocedureManager::instance().getProcFile(m_procedure);'''
    assert source.count(before) == 1
    return source.replace(before, after).encode()
