"""Hash-checked CPython 3.13 native port. SPDX-License-Identifier: GPL-3.0-or-later."""
import hashlib
from pathlib import Path

PREIMAGES = {
    'lib/SPELL_EXC/src/SPELLvariableMonitor.C': '7162c7a9abab73cb9b9e20bc34f8e32185d6a4ab728e12d80989bf64bcb27aa7',
    'lib/SPELL_WS/src/SPELLwsStorage.C': '85fff1d7e917ce5913daaf99ecb385362a2f5323d49d7d41de8125b1e13ee34f',
    'lib/SPELL_EXC/src/SPELLgoto.C': '6ff696df62c225f7adb17d12dd0e8581988eb0bf327105c45d07ebbacae4560f',
    'lib/SPELL_EXC/src/SPELLastAnalyzer.C': '5f5ab545c54e182c5b4b74feaae7ee386bb5d926f85b066dfe38b5ad73de59af',
    'include/SPELL_EXC/SPELLastAnalyzer.H': '7ad2a805f8b499b3438c8b2c848b5cc36129388bd0027bc7c9e749f417dba1f1',
    'lib/SPELL_EXC/src/SPELLlnotab.C': '5c7598a5444bde5cde810a8335081f8b683579e874e6958ab678999c8e17c5f3',
    'include/SPELL_EXC/SPELLlnotab.H': '9ed4e9b200153a3c52d29ba9c0d2f2add53f1001acd244ff55cad25d78b188a4',
    'include/SPELL_UTIL/SPELLpythonMonitors.H': 'ff0f9af10116d360b85ea19b3479da94a4df856c95e2c0067c35fbe871caff19',
    'lib/SPELL_UTIL/src/SPELLpythonHelper.C': '2610cab71f4d339ff33ffaa90486deaa060cf3060435a433b8f888c72824d837',
    'lib/SPELL_UTIL/src/SPELLutils.C': 'ee16758649173ca2c838545f43d6d44dfbd5264bc25bb1fa2257b4ffdd509d70',
    'lib/SPELL_UTIL/src/SPELLerror.C': 'e95b2787936e7ee0b56d5e956e6ba07db138dbab13abfec2dc07ef6a859f3f93',
    'include/SPELL_UTIL/SPELLpythonHelper.H': '4e28c64ccdfeb24c9e855339b2d3b4d6f89caa03216ec9a4730189a635ff139a',
    'lib/SPELL_UTIL/src/SPELLlogPython.C': '2d98e6606c3c9e7a8eada2bd56fe9784547209a9d48644eac24b055234883be4',
}
ROOT = Path(__file__).resolve().parent / 'native'


def section(text, start, end, body):
    assert text.count(start) == 1, start
    a = text.index(start)
    b = text.index(end, a)
    assert a < b
    return text[:a] + body + '\n' + text[b:]


def body(name):
    return (ROOT / name).read_text(encoding='utf-8')


def apply(name, original):
    if name not in PREIMAGES:
        return original
    if hashlib.sha256(original).hexdigest() != PREIMAGES[name]:
        raise ValueError('Native preimage differs: ' + name)
    text = original.decode('utf-8')
    if name.endswith('SPELLvariableMonitor.C'):
        marker = '// GLOBALS '
        assert text.count(marker) == 1
        text = text[:text.index(marker)] + '#include "SPELL_UTIL/SPELLpython313.H"\n#include <functional>\n' + body('variable_monitor.cpp')
    elif name.endswith('SPELLwsStorage.C'):
        marker = '#define LATEST_MARSHAL_VERSION 2'
        assert text.count(marker) == 1
        text = text[:text.index(marker)] + '''#include "SPELL_UTIL/SPELLpython313.H"
#include <charconv>
#include <cstdint>
#include <zlib.h>
''' + body('ws_storage.cpp')
    elif name.endswith('SPELLgoto.C'):
        text = section(text, '#include "opcode.h"', '// CONSTRUCTOR    : SPELLgoto::SPELLgoto',
                       '#include "SPELL_UTIL/SPELLpython313.H"\n#include "SPELL_UTIL/SPELLpythonHelper.H"\n\n//=============================================================================')
        text = section(text, 'void SPELLgoto::analyze()', 'std::string SPELLgoto::validateGotos()',
                       body('analyze_goto.cpp') + '\n//=============================================================================\n')
        text = text.replace('return (*lit).second;', 'return lit == m_labels.end() ? -1 : static_cast<int>(lit->second);')
    elif name.endswith('SPELLastAnalyzer.H'):
        text = text.replace('void findNodeLines( struct _node* node, unsigned int depth, unsigned int& parDepth, NodeInfo& info );',
                            '// Tokenization replaces the removed private parser node API.')
        text = text.replace('NodeInfo m_currentNode;', 'NodeInfo m_currentNode{};')
    elif name.endswith('SPELLastAnalyzer.C'):
        text = text.replace('#include "node.h"\n#include "token.h"', '#include "SPELL_UTIL/SPELLpython313.H"\n#include <algorithm>')
        text = section(text, 'void SPELLastAnalyzer::process(', 'bool SPELLastAnalyzer::isSimpleLine(',
                       body('analyze_source.cpp') + '\n//============================================================================\n')
    elif name.endswith('SPELLlnotab.H'):
        text = text.replace('return m_lines.front();', 'return m_lines.empty() ? -1 : m_lines.front();')
    elif name.endswith('SPELLlnotab.C'):
        text = text.replace('#include "SPELL_EXC/SPELLlnotab.H"', '#include "SPELL_EXC/SPELLlnotab.H"\n#include "SPELL_UTIL/SPELLpython313.H"\n#include "SPELL_UTIL/SPELLpythonHelper.H"')
        text = section(text, 'void SPELLlnotab::analyze(', 'const int SPELLlnotab::lineAfter(',
                       body('analyze_lines.cpp') + '\n//============================================================================\n')
    elif name.endswith('SPELLpythonMonitors.H'):
        text = section(text, '\tvirtual ~SPELLsafePythonOperations()', '\nprivate:', '''
    virtual ~SPELLsafePythonOperations() noexcept(false)
    {
        // Do not throw a second exception during C++ stack unwinding.
        try {
            if (std::uncaught_exceptions() == 0)
                SPELLpythonHelper::instance().checkError();
        } catch (...) {
            SPELLpythonHelper::instance().releaseGIL(m_state);
            throw;
        }
        SPELLpythonHelper::instance().releaseGIL(m_state);
    };
''')
    elif name.endswith('SPELLpythonHelper.H'):
        text = text.replace('#define __SPELL_PYHELPER_H__', '#define __SPELL_PYHELPER_H__\n#include <thread>')
        text = text.replace('bool m_initialized;', '''bool m_initialized;
        bool m_ownsInterpreter = false;
        std::thread::id m_ownerThread;
        PyThreadState* m_embeddedThread = nullptr;''')
    elif name.endswith('SPELLpythonHelper.C'):
        text = text.replace('#include "Python-ast.h"', '#include "SPELL_UTIL/SPELLpython313.H"\n#include <memory>')
        text = text.replace('#    include "code.h"\n', '')
        text = section(text, 'PyCodeObject* SPELLpythonHelper::compile(',
                       'PyFrameObject* SPELLpythonHelper::createFrame(',
                       body('helper_compile.cpp') + '\n//=============================================================================\n')
        text = section(text, 'void SPELLpythonHelper::initialize()',
                       'bool SPELLpythonHelper::isInstance( PyObject* object, const std::string& className',
                       body('helper_lifecycle.cpp') + '\n//=============================================================================\n')
        text = section(text, 'void SPELLpythonHelper::checkError()',
                       '// METHOD    : SPELLpythonHelper::newInstance', '''void SPELLpythonHelper::checkError()
{
    SPELLpython313::GIL gil;
    std::unique_ptr<SPELLcoreException> error(SPELLerror::instance().errorToException());
    if (error) throw *error;
}
\n//=============================================================================\n''')
        text = text.replace('PyEval_CallObjectWithKeywords(', 'PyObject_Call(')
        text = text.replace('    Py_XINCREF(result);\n    DEBUG("[PYH] New instance end', '    DEBUG("[PYH] New instance end')
        text = text.replace('    Py_INCREF(moduleObj);\n    DEBUG("[PYH] Get module done', '    DEBUG("[PYH] Get module done')
        text = text.replace('    PyObject* moduleObj = getModule(module);',
                            '    SPELLpython313::Owned moduleOwner(getModule(module));\n    PyObject* moduleObj = moduleOwner.get();')
    elif name.endswith('SPELLutils.C'):
        text = text.replace('#include "SPELL_UTIL/SPELLbase.H"', '#include "SPELL_UTIL/SPELLbase.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        text = section(text, 'void SPELLutils::dumpInterpreterInfo(',
                       '// FUNCTION:    SPELLutils::dumpString()',
                       body('dump_state.cpp') + '\n//============================================================================\n')
    elif name.endswith('SPELLlogPython.C'):
        text = text.replace('static PyObject* KEY_SEVERITY = STRPY("severity");\nstatic PyObject* KEY_LEVEL    = STRPY("level");',
                            '// Keyword lookup must not allocate Python objects before Py_Initialize.')
        text = text.replace('PyDict_Contains( kargs, KEY_SEVERITY )', 'PyDict_GetItemString( kargs, "severity" ) != nullptr')
        text = text.replace('PyDict_Contains( kargs, KEY_LEVEL )', 'PyDict_GetItemString( kargs, "level" ) != nullptr')
    elif name.endswith('SPELLerror.C'):
        text = text.replace('#include "SPELL_UTIL/SPELLerror.H"', '#include "SPELL_UTIL/SPELLerror.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        # These two objects are never read. They leaked interpreter-owned types
        # across finalization; the actual control protocol uses RuntimeError.
        text = text.replace('    PyType_Ready(&ExecutionAborted_Type);\n    m_excExecutionAborted = (PyObject*) PyObject_New( PyExecutionAbortedObject, &ExecutionAborted_Type );\n    PyType_Ready(&ExecutionTerminated_Type);\n    m_excExecutionTerminated = (PyObject*) PyObject_New( PyExecutionTerminatedObject, &ExecutionTerminated_Type );',
                            '    m_excExecutionAborted = nullptr;\n    m_excExecutionTerminated = nullptr;')
        text = section(text, 'SPELLcoreException* SPELLerror::errorToException()',
                       '// METHOD    : SPELLerror::throwSyntaxException',
                       body('error_conversion.cpp') + '\n//=============================================================================\n')
        text = text.replace('PYSTR(tb->tb_frame->f_code->co_filename)', 'SPELLpython313::filename(tb->tb_frame)')
        # The remaining getPythonError fetch owns its three references.
        needle = 'PyErr_Fetch( &ptype, &pvalue, &ptraceback );'
        assert text.count(needle) == 1
        text = text.replace(needle, needle + '''
        SPELLpython313::Owned typeOwner(ptype), valueOwner(pvalue), tracebackOwner(ptraceback);''')
        text = text.replace('DEBUG("[ERR] Error already tracked");\n\t\t\treturn;',
                            'DEBUG("[ERR] Error already tracked");\n\t\t\tdelete exc;\n\t\t\treturn;')
    return text.encode('utf-8')


def apply_tree(source):
    changed = {}
    for name, before in PREIMAGES.items():
        path = source / name
        updated = apply(name, path.read_bytes())
        path.write_bytes(updated)
        changed[name] = {'upstream_sha256': before, 'sha256': hashlib.sha256(updated).hexdigest()}
    header = source / 'include/SPELL_UTIL/SPELLpython313.H'
    header.write_bytes((ROOT / header.name).read_bytes())
    changed[header.relative_to(source).as_posix()] = {
        'new': True, 'sha256': hashlib.sha256(header.read_bytes()).hexdigest()}
    return changed
