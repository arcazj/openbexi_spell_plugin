"""Protect the native CIF execution-count read against interpreter trace reset.

SPDX-License-Identifier: GPL-3.0-or-later
Candidate correction for the retained v0.6 startup ASan failure. Trace models
belong to the GIL-owning evaluator; an IPC status worker must hold that same
lock until it has copied the count out of the borrowed trace reference.
"""
import hashlib

SOURCE = 'lib/SPELL_CIF/src/SPELLcif.C'
ORIGINAL = '203bf8e38160e92770791a90bdf2339cb774ecdaf6bbe77ec3037f5162e3560f'
PORTED = '660c14966413249167ce24c650cd3fea6f99e15302e3b2de1860574631ed8f21'


def apply(name, original, ported):
    if (name != SOURCE or hashlib.sha256(original).hexdigest() != ORIGINAL
            or hashlib.sha256(ported).hexdigest() != PORTED):
        raise ValueError('Unexpected CIF trace-read preimage')
    text = ported.decode('utf-8')
    anchor = 'unsigned int SPELLcif::getNumExecutions() const\n{\n'
    if text.count(anchor) != 1:
        raise ValueError('Expected exactly one native execution-count reader')
    text = text.replace(anchor, anchor + '''    // IPC status notifications run without the evaluator GIL. Keep the trace
    // reference alive through the count read while reset clears the map.
    SPELLpython313::GIL traceRead;
''')
    return ('#include "SPELL_UTIL/SPELLpython313.H"\n' + text).encode('utf-8')
