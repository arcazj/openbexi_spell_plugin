"""Publish trace counts without borrowing trace storage or taking the GIL.

SPDX-License-Identifier: GPL-3.0-or-later
Evaluator-owned mutations publish a scalar snapshot. Background CIF workers
only load the atomic value, so they cannot race trace reset or invert the
GIL/display-buffer lock order. Frame manager input includes checkpoint fixes.
"""
import hashlib

SOURCE = 'lib/SPELL_CIF/src/SPELLcif.C'
ORIGINAL = '203bf8e38160e92770791a90bdf2339cb774ecdaf6bbe77ec3037f5162e3560f'
PORTED = '660c14966413249167ce24c650cd3fea6f99e15302e3b2de1860574631ed8f21'
PREIMAGES = {
    SOURCE: (ORIGINAL, PORTED),
    'include/SPELL_EXC/SPELLframeManager.H': (
        '4c265b25b8e311bef3ff2bf08374e023160346c97d27883b086882daac3602b5',
        '2b256af6396a1aaad6bb7e3ab3c1253205b1bde673d3dceba98d9253548dc4a4'),
    'lib/SPELL_EXC/src/SPELLframeManager.C': (
        'ae618d8e3239377b76d5e6e37782efc893e723dfc9c3daa8d89bb998cb6e1402',
        'b0e8757c78d15479ec88d22497bbbef7706a70b41954211d44cebde6c6a4d9a7'),
    'lib/SPELL_EXC/src/SPELLcallstack.C': (
        '8ceb19ddd2af71c4780042d0fcc1dfcfd107c2cbcda5a8fbe76cfa038227a931',
        '8ceb19ddd2af71c4780042d0fcc1dfcfd107c2cbcda5a8fbe76cfa038227a931'),
}


def apply(name, original, ported):
    expected = PREIMAGES.get(name)
    if expected != (hashlib.sha256(original).hexdigest(), hashlib.sha256(ported).hexdigest()):
        raise ValueError('Unexpected trace snapshot preimage: ' + name)
    text = ported.decode('utf-8')
    def replace(before, after, count=1):
        nonlocal text
        if text.count(before) != count:
            raise ValueError('Trace snapshot anchor differs: ' + before)
        text = text.replace(before, after)
    if name == SOURCE:
        replace('getCurrentTraceModel().getCurrentLineExecutions()', 'getPublishedTraceExecutions()')
    elif name.endswith('SPELLframeManager.H'):
        text = '#include <atomic>\n' + text
        replace('SPELLexecutionTrace& getCurrentTraceModel();',
            'SPELLexecutionTrace& getCurrentTraceModel();\n'
            '        unsigned int getPublishedTraceExecutions() const { return m_publishedExecutions.load(std::memory_order_relaxed); }\n'
            '        void publishTraceExecutions() { m_publishedExecutions.store(getCurrentTraceModel().getCurrentLineExecutions(), std::memory_order_relaxed); }')
        replace('TraceMap              m_traceMap;',
            'std::atomic<unsigned int> m_publishedExecutions{0};\n\t\tTraceMap              m_traceMap;')
    elif name.endswith('SPELLframeManager.C'):
        replace('return m_traceMap.find(codeId)->second;',
            'm_publishedExecutions.store(0, std::memory_order_relaxed);\n\t\treturn m_traceMap.find(codeId)->second;')
        # Restrict the return replacement to the trace getter, not model lookup.
        begin = text.index('SPELLexecutionTrace& SPELLframeManager::getTraceModel(')
        end = text.index('SPELLexecutionTrace& SPELLframeManager::getCurrentTraceModel()', begin)
        chunk = text[begin:end]
        if chunk.count('return it->second;') != 1: raise ValueError('Trace return differs')
        text = text[:begin] + chunk.replace('return it->second;',
            'm_publishedExecutions.store(it->second.getCurrentLineExecutions(), std::memory_order_relaxed);\n\t\treturn it->second;') + text[end:]
        replace('m_traceMap.clear();', 'm_traceMap.clear(); m_publishedExecutions.store(0, std::memory_order_relaxed);', 3)
        replace('m_traceMap.erase(tit);',
            'm_traceMap.erase(tit);\n            if (m_currentTraceModel == currentModelId) m_publishedExecutions.store(0, std::memory_order_relaxed);')
    else:
        for mutation in ('getCurrentTraceModel().markExecuted();',
                         'getTraceModel(file).setCurrentLine(line);',
                         'getCurrentTraceModel().setCurrentLine(line);'):
            replace(mutation, mutation + '\n        SPELLexecutor::instance().getFrameManager().publishTraceExecutions();')
    return text.encode('utf-8')
