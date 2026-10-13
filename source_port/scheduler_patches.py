"""Checked original scheduler corrections; original notices remain intact.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib

PREIMAGES={
    'lib/SPELL_EXC/src/SPELLexecutorUtils.C':(
        '490f2df621ba492c7a92f479e8669cdb6a6183d96ad71b2d48e2404265dd850d',
        '490f2df621ba492c7a92f479e8669cdb6a6183d96ad71b2d48e2404265dd850d'),
    'lib/SPELL_EXC/src/SPELLexecutorPython.C':(
        '89abec69514d3022550ef4f39264895a5fc9df18bff82b7a7ff535389b66e33e',
        '8fe2ff2c9e80fb93d7437a05c62e7a7cae13e30b20bfc6258a4820f601d995d6'),
    'lib/SPELL_EXC/src/SPELLscheduler.C':(
        '2d00d9b9d5e5296799582e7937873639ca4400eb204fec174317b29c36bdd50a',
        '7ae4398e50ffa06a3efd3b53921ea233156e471c8e894b5ef33a579c8aa06179')}


def apply(name,original,ported):
    assert PREIMAGES.get(name)==(hashlib.sha256(original).hexdigest(),hashlib.sha256(ported).hexdigest()),name
    text=ported.decode('utf-8')
    def once(before,after):
        nonlocal text
        assert text.count(before)==1,(name,before)
        text=text.replace(before,after)
    if name.endswith('SPELLexecutorUtils.C'):
        once('condition.targetTime = arguments.getModifier_Until();',
             '// Use the same absolute/type validation as an argument-based time wait.\n\t\tsetTimeCondition( arguments, condition );')
    elif name.endswith('SPELLexecutorPython.C'):
        begin=text.index('static PyObject* Executor_StartWait( PyObject* self, PyObject* args )\n{')
        end=text.index('    Py_RETURN_NONE;',begin)
        body=text[begin:end]
        before='catch(SPELLcoreException& ex)\n    {\n'
        assert body.count(before)==1
        body=body.replace(before,before+'        // A failed Python TIME conversion may leave its exception pending.\n        // Clear it before constructing the public SPELL exception below.\n        PyErr_Clear();\n')
        text=text[:begin]+body+text[end:]
    elif name.endswith('SPELLscheduler.C'):
        once('(m_notificationPeriod>0) &&','(m_notificationPeriod>SPELLtime(0,0,true)) &&')
    else:raise ValueError(name)
    return text.encode('utf-8')
