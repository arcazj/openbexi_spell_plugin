"""Hash-checked CPython 3.13 native port. SPDX-License-Identifier: GPL-3.0-or-later."""
import hashlib
import re
from pathlib import Path

PREIMAGES = {
    'include/SPELL_EXC/SPELLframeManager.H': '4c265b25b8e311bef3ff2bf08374e023160346c97d27883b086882daac3602b5',
    'include/SPELL_EXC/SPELLexecutor.H': '6671885f2423ea99d080e0f06049a91b0fee3352e7e0469b19467f53ecb8cb01',
    'include/SPELL_DTA/SPELLdtaContainer.H': 'bf2de9f9ef83507f86acde77e8c5d896009bca6b1c616c809dcab9e53f6e7a07',
    'include/SPELL_DTA/SPELLdtaVariable.H': 'dfbc1e34ae04f9713bf80f4b2edef8fb5c09e678795046a1ce58f88789d915f0',
    'lib/SPELL_DTA/src/SPELLdtaContainer.C': 'c0dbe9140ac7934f0e6af0688ec44ca49962e36204977b0d53ea78f656197050',
    'lib/SPELL_DTA/src/SPELLdtaContainerObjectMethods.C': 'd8acdcadff6d1881cd61fd4447c8fa43b19292eb1c9b077c613856e55bbdb6b6',
    'lib/SPELL_DTA/src/SPELLdtaModule.C': '41fc9488d7f4831eb1d60a94ddf068fbd96698003ee24e37e22a0376dd728e0f',
    'lib/SPELL_DTA/src/SPELLdtaVariable.C': '1fc250c12a0e5dce65471c8a9fa4b4a31fc377bb77e8dce8aeddeebb0b60913e',
    'lib/SPELL_DTA/src/SPELLdtaVariableObjectMethods.C': 'a1de382ba85e164f02f3b9a7ef9d59d9fd8c6aa447a56601056b94a3c2fe63ac',
    'lib/SPELL_WRP/src/SPELLpyValue.C': 'd641a196503bb44286030f27fcc66b39b42159e71e60c9aa8f7a20ccd6407eba',
    'lib/SPELL_EXC/src/SPELLframeManager.C': 'ae618d8e3239377b76d5e6e37782efc893e723dfc9c3daa8d89bb998cb6e1402',
    'include/SPELL_WS/SPELLwsWarmStartImpl.H': '70692486c7a89222fa682ee0aee82a19e7d43a97381aedfd5623e1370a12b7cf',
    'lib/SPELL_WS/src/SPELLwsWarmStartImpl.C': 'b0bb02ac4636ae398ed57fcfed3d4ef2cb35b5f19f03c1b8300c2fe5b1e163f6',
    'lib/SPELL_EXC/src/SPELLexecutionModel.C': '45545e623c76fcf2d0817ed761f262a835479e08adeaf0658bb3f956b94c5038',
    'lib/SPELL_EXC/src/SPELLexecutorImpl.C': '3a891afdf5e0dbcd75f97db263e3c30311c597872e434fc91b6c993683b2b0df',
    'lib/SPELL_EXC/src/SPELLserviceImpl.C': '9e56ddfa666429777f37ab7bedb76de9a539145050123096554339bb1ea40382',
    'lib/SPELL_EXC/src/SPELLbytecode.C': 'ab9e4c3accad70a664cfbfff43da74686777213f0ec98cd85250f73df04fcd60',
    'include/SPELL_EXC/SPELLbytecode.H': 'ade8253aa4387aa5f0fa633a31ec6e1689eb88fc960fb64ece274427141eeb18',
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
    if name.endswith('SPELLframeManager.H'):
        text = text.replace('#include "SPELL_EXC/SPELLexecutionModel.H"', '#include "SPELL_EXC/SPELLexecutionModel.H"\n#include "SPELL_EXC/SPELLexecutorConfiguration.H"')
        text = text.replace('void initialize( const std::string& scriptFile );', '''void initialize( const std::string& scriptFile );
        void initialize(const std::string& scriptFile, const SPELLexecutorConfig& configuration);''')
        text = text.replace('bool                  m_terminated;', 'bool                  m_terminated;\n        bool m_resumePending; // saved continuations require the modern WS adapter')
    elif name.endswith('SPELLexecutor.H'):
        text = text.replace('static inline SPELLexecutorIF& instance()', 'static bool isAvailable() { return s_instance != nullptr; }\n\n        static inline SPELLexecutorIF& instance()')
    elif name.endswith('SPELLdtaContainer.H'):
        text = text.replace('void incref();', 'void clear(bool releaseValues = true); // detach borrowed links, optionally clear values')
        text = text.replace('std::vector<std::string> m_varOrder;', '// Python 3 dictionaries preserve insertion order and key identity.')
    elif name.endswith('SPELLdtaVariable.H'):
        text = text.replace('void setContainer( SPELLdtaContainer* container );', '''void setContainer( SPELLdtaContainer* container );
        void detachContainer(SPELLdtaContainer* expected) { if (m_container == expected) m_container = nullptr; }''')
    elif name.endswith(('SPELLdtaContainer.C', 'SPELLdtaContainerObjectMethods.C', 'SPELLdtaVariableObjectMethods.C')):
        replacement = {'SPELLdtaContainer.C':'dta_container.cpp',
            'SPELLdtaContainerObjectMethods.C':'dta_container_bindings.cpp',
            'SPELLdtaVariableObjectMethods.C':'dta_variable_bindings.cpp'}[Path(name).name]
        text = text[:text.index('// FILES TO INCLUDE')] + body(replacement)
    elif name.endswith('SPELLdtaModule.C'):
        # Retain the original public method tables; allocate types per interpreter.
        marker = '//============================================================================\n// Python type specification'
        assert marker in text
        text = text[:text.index(marker)] + body('dta_module.cpp')
    elif name.endswith('SPELLdtaVariable.C'):
        text = text.replace('#include "SPELL_DTA/SPELLdtaVariable.H"', '#include "SPELL_DTA/SPELLdtaVariable.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
        text = section(text, '\t\t\tint longValue = 0;', '\n\t\t}\n\n\t\tm_value = value;', '''            double numeric = PyLong_AsDouble(pyValue);
            if (PyErr_Occurred()) SPELLpythonHelper::instance().checkError();
            SPELLpython313::Owned converted(PyFloat_FromDouble(numeric));
            if (!converted.get()) SPELLpythonHelper::instance().checkError();
            value = converted.get();''')
        guard = '''
    if (!SPELLexecutor::isAvailable())
        THROW_EXCEPTION("SPELL executor unavailable", "Data notifications and prompts require an active executor", SPELL_ERROR_EXECUTION);
'''
        text = text.replace('\tm_name = "";', '\tif (kwds && SPELLdtaContainer::areGlobalnotificationsEnabled()) { ' + guard + ' }\n\tm_name = "";', 1)
        text = text.replace('bool SPELLdtaVariable::shouldNotify()\n{', 'bool SPELLdtaVariable::shouldNotify()\n{\n    if (!SPELLdtaContainer::areGlobalnotificationsEnabled()) return false;' + guard)
        text = text.replace('bool SPELLdtaVariable::promptForValue( std::string& message )\n{', 'bool SPELLdtaVariable::promptForValue( std::string& message )\n{' + guard)
        text = text.replace('PyObject* SPELLdtaVariable::confirmValue()\n{', 'PyObject* SPELLdtaVariable::confirmValue()\n{' + guard)
    elif name.endswith('SPELLpyValue.C'):
        text = text.replace('#include "SPELL_WRP/SPELLpyValue.H"', '#include "SPELL_WRP/SPELLpyValue.H"\n#include "SPELL_UTIL/SPELLpython313.H"\n#include <algorithm>')
        text = text.replace('m_stringValue = PYSTR(pyValue);', 'm_stringValue = SPELLpython313::text(pyValue);')
        text = text.replace('PYSSTR(key), SPELLpyValue(value)', 'SPELLpython313::text(key), SPELLpyValue(value)')
        text = text.replace('return SSTRPY(m_stringValue);', 'return PyUnicode_FromStringAndSize(m_stringValue.data(), m_stringValue.size());')
        text = text.replace('void SPELLpyValue::set( PyObject* pyValue )\n{', '''void SPELLpyValue::set( PyObject* pyValue )
{
    static thread_local std::vector<PyObject*> active;
    struct Recursion {
        std::vector<PyObject*>& stack;
        Recursion(std::vector<PyObject*>& values, PyObject* object): stack(values) {
            if (stack.size() >= 128 || std::find(stack.begin(), stack.end(), object) != stack.end()) {
                PyErr_SetString(PyExc_ValueError, "SPELL values cannot be cyclic or nested beyond 128 levels");
                SPELLpythonHelper::instance().checkError();
            }
            if (Py_EnterRecursiveCall(" while converting a SPELL value")) SPELLpythonHelper::instance().checkError();
            stack.push_back(object);
        }
        ~Recursion() { stack.pop_back(); Py_LeaveRecursiveCall(); }
    } recursion(active, pyValue);
    m_listValue.clear();
    m_dictValue.clear();''')
        text = text.replace('\t\t\tPy_INCREF(item);\n', '')
        text = text.replace('\t\t\tPyDict_SetItemString(dict,key.c_str(),item);', '''            SPELLpython313::Owned pyKey(PyUnicode_FromStringAndSize(key.data(), key.size()));
            if (!item || !pyKey.get() || PyDict_SetItem(dict,pyKey.get(),item)<0) {
                Py_XDECREF(item); Py_DECREF(dict); return nullptr;
            }
            Py_DECREF(item);''')
        text = text.replace('\t\t\tPyList_SetItem(list,idx,item);', '''            if (!item) { Py_DECREF(list); return nullptr; }
            PyList_SET_ITEM(list,idx,item);''')
        text = text.replace('PyObject* list = PyList_New(m_listValue.size());', 'PyObject* list = PyList_New(m_listValue.size());\n        if (!list) return nullptr;')
        text = text.replace('PyObject* dict = PyDict_New();', 'PyObject* dict = PyDict_New();\n        if (!dict) return nullptr;')
        start = 'SPELLpyValue& SPELLpyValue::operator=( const SPELLpyValue& other )'
        assert text.count(start) == 1
        text = text[:text.index(start)] + body('py_value_assignment.cpp')
    elif name.endswith('SPELLframeManager.C'):
        text = text.replace('#include "SPELL_EXC/SPELLframeManager.H"', '#include "SPELL_EXC/SPELLframeManager.H"\n#include "SPELL_UTIL/SPELLpython313.H"\n#include <memory>\n#include <sys/time.h>')
        text = section(text, 'SPELLframeManager::~SPELLframeManager()', 'void SPELLframeManager::initialize(', '''SPELLframeManager::~SPELLframeManager()
{
    // Destruction must not compile a new procedure. The interpreter owns WS;
    // models and the initial-frame slot each own their own frame references.
    for (const auto& item: m_modelMap) delete item.second;
    m_modelMap.clear();
    m_modelKeys.clear();
    m_traceMap.clear();
    m_model = nullptr;
    m_currentFrame = nullptr; // borrowed from an initial frame or model
    Py_XDECREF(m_definitions);
    Py_XDECREF(m_code);
    Py_XDECREF(m_initialFrame);
}
\n//=============================================================================\n''')
        text = text.replace('        Py_XDECREF(m_currentFrame);\n', '')
        text = text.replace('\t\tPy_INCREF(m_currentFrame);\n', '')
        text = text.replace('    m_terminated = false;', '    m_terminated = false;\n    m_resumePending = false;')
        text = text.replace('    m_model = NULL;\n\n    DEBUG("[EF] Clearing breakpoints");', '    m_model = NULL;\n    m_currentFrame = nullptr;\n\n    DEBUG("[EF] Clearing breakpoints");')
        text = section(text, 'void SPELLframeManager::initialize(', 'void SPELLframeManager::saveState()', '''void SPELLframeManager::initialize(const std::string& scriptFile)
{
    initialize(scriptFile, SPELLexecutor::instance().getConfiguration());
}
void SPELLframeManager::initialize(const std::string& scriptFile, const SPELLexecutorConfig& configuration)
{
    m_filename = scriptFile;
    SPELLvariableMonitor::s_enabled = configuration.isWatchEnabled();
    SPELLresourceMonitor::s_enabled = configuration.isResourcesDisplayEnabled();
    reset();
}
\n//=============================================================================\n''')
        text = text.replace('m_initialFrame = m_warmStart->restoreState();', 'm_resumePending = true;\n        m_initialFrame = m_warmStart->restoreState();')
        text = text.replace('m_initialFrame = m_warmStart->fixState();', 'm_resumePending = true;\n        m_initialFrame = m_warmStart->fixState();')
        text = section(text, 'const SPELLexecutionResult SPELLframeManager::execute()', 'void SPELLframeManager::checkRuntimeError()', body('frame_manager_execute.cpp'))
        text = text.replace('SPELLwsWarmStartImpl::setGlobalsFilter( PyDict_Keys(mainDict) );', '''SPELLpython313::Owned filterKeys(PyDict_Keys(mainDict));
    if (!filterKeys.get()) SPELLpythonHelper::instance().checkError();
    SPELLwsWarmStartImpl::setGlobalsFilter(filterKeys.get());''')
        text = section(text, 'void SPELLframeManager::runScript(', 'void SPELLframeManager::callbackEventCall(', body('frame_manager_script.cpp'))
        text = section(text, 'void SPELLframeManager::copyDatabase(', 'void SPELLframeManager::updateDatabases(', body('frame_manager_database.cpp'))
        text = section(text, 'void SPELLframeManager::updateDefinitions(', 'void SPELLframeManager::createFrameModel(', body('frame_manager_definitions.cpp'))
        # Hold every back-frame reference throughout model reconstruction.
        text = text.replace('PyFrameObject* currentFrame = m_initialFrame;', '''std::vector<std::unique_ptr<SPELLpython313::Owned>> frameOwners;
        PyFrameObject* currentFrame = reinterpret_cast<PyFrameObject*>(Py_XNewRef(m_initialFrame));''')
        text = text.replace('frames.push_back(currentFrame);', '''frameOwners.push_back(std::make_unique<SPELLpython313::Owned>(reinterpret_cast<PyObject*>(currentFrame)));
            frames.push_back(currentFrame);''')
        text = text.replace('currentFrame = currentFrame->f_back;', 'currentFrame = PyFrame_GetBack(currentFrame);')
        text = text.replace('PyFrameObject* frame = m_initialFrame;', '''SPELLpython313::Owned frameOwner(Py_XNewRef(m_initialFrame));
    PyFrameObject* frame = m_initialFrame;''')
        text = text.replace('frame = frame->f_back;', '''frameOwner.reset(reinterpret_cast<PyObject*>(PyFrame_GetBack(frame)));
        frame = reinterpret_cast<PyFrameObject*>(frameOwner.get());''')
        text = text.replace('PyEval_EvalFrame( frame );', 'SPELLpython313::Owned result(PyEval_EvalFrame(frame));')
        text = re.sub(r'^.*DEBUG\("Frame (?:stack top|value stack).*\n', '', text, flags=re.M)
        text = text.replace('PYCREPR(frame->f_back)', 'SPELLpython313::text(SPELLpython313::Owned(reinterpret_cast<PyObject*>(PyFrame_GetBack(frame))).get())')
        text = re.sub(r'PY(?:STR|REPR)\((\w+)->f_code->co_filename\)', r'SPELLpython313::filename(\1)', text)
        text = re.sub(r'PYSTR\((\w+)->f_code->co_name\)', r'SPELLpython313::codename(\1)', text)
        text = re.sub(r'\b(\w+)->f_code\b', r'SPELLpython313::FrameCode(\1).get()', text)
        text = re.sub(r'\b(\w+)->f_lineno\b', r'PyFrame_GetLineNumber(\1)', text)
        text = re.sub(r'\b(\w+)->f_lasti\b', r'PyFrame_GetLasti(\1)', text)
        text = re.sub(r'\b(\w+)->f_globals\b', r'SPELLpython313::FrameGlobals(\1).get()', text)
        text = re.sub(r'^\s*PyFrame_(?:FastToLocals|LocalsToFast)\([^;]+;\n', '\n', text, flags=re.M)
        text = section(text, 'void SPELLframeManager::filterDictUpdated()', 'const bool SPELLframeManager::setNewLine(', '''void SPELLframeManager::filterDictUpdated()
{
    PyObject* definitions = PyDict_Keys(SPELLpythonHelper::instance().getMainDict());
    if (!definitions) SPELLpythonHelper::instance().checkError();
    Py_XDECREF(m_definitions);
    m_definitions = definitions;
}
\n//=============================================================================\n''')
    elif name.endswith('SPELLwsWarmStartImpl.H'):
        text = text.replace('#include "SPELL_WS/SPELLwsFrame.H"', 'class SPELLwsFrame; // Private implementation dependency, not required by callers.')
        text = text.replace('\t\tstatic PyObject* s_filterKeys;', '// Filter ownership is per interpreter; see ws_filter.cpp.')
    elif name.endswith('SPELLwsWarmStartImpl.C'):
        text = text.replace('#include "SPELL_WS/SPELLwsWarmStartImpl.H"', '#include "SPELL_WS/SPELLwsWarmStartImpl.H"\n#include "SPELL_WS/SPELLwsFrame.H"')
        text = text.replace('PyObject* SPELLwsWarmStartImpl::s_filterKeys = 0;', '')
        marker = '//=============================================================================\n// STATIC : SPELLwsWarmStartImpl::setGlobalsFilter()'
        assert text.count(marker) == 1
        text = text[:text.index(marker)] + '// Filter methods are compiled from ws_filter.cpp.\n'
    elif name.endswith(('SPELLexecutionModel.C', 'SPELLexecutorImpl.C', 'SPELLserviceImpl.C')):
        text = text.replace('// GLOBALS ', '#include "SPELL_UTIL/SPELLpython313.H"\n\n// GLOBALS ', 1)
        text = text.replace('PYSTR(frame->f_code->co_filename)', 'SPELLpython313::filename(frame)')
        text = text.replace('PYSTR(frame->f_code->co_name)', 'SPELLpython313::codename(frame)')
        text = text.replace('frame->f_lineno', 'PyFrame_GetLineNumber(frame)')
        text = text.replace('frame->f_code', 'SPELLpython313::FrameCode(frame).get()')
        if name.endswith('SPELLexecutionModel.C'):
            text = text.replace('\tm_modelId = modelId;', '\tPy_INCREF(m_frame);\n\tm_modelId = modelId;')
            text = text.replace('SPELLexecutionModel::~SPELLexecutionModel()\n{\n}', 'SPELLexecutionModel::~SPELLexecutionModel()\n{\n    Py_XDECREF(m_frame);\n}')
    elif name.endswith('SPELLbytecode.H'):
        text = text.replace('unsigned int end_lineno;', '''unsigned int end_lineno;
            unsigned int body_lineno;
            unsigned int finally_lineno;
            unsigned int finally_end_lineno;
            std::vector<std::pair<unsigned int,unsigned int>> except_ranges;''')
    elif name.endswith('SPELLbytecode.C'):
        text = section(text, '#include "opcode.h"', '// CONSTRUCTOR',
                       '#include "SPELL_UTIL/SPELLanalysis313.H"\n\n//=============================================================================\n')
        text = section(text, 'void SPELLbytecode::analyze()', 'bool SPELLbytecode::isExecutable(',
                       body('analyze_bytecode.cpp') + '\n//=============================================================================\n')
        text = text.replace('(it->try_lineno < lineNo) && (it->end_try_lineno >= lineNo)',
                            '(it->body_lineno <= lineNo) && (it->end_try_lineno >= lineNo)')
        text = section(text, 'bool SPELLbytecode::isInExceptBlock(', 'bool SPELLbytecode::isInFinallyBlock(', '''bool SPELLbytecode::isInExceptBlock(unsigned int lineNo) const {
    for (const auto& block: m_tryBlocks)
        for (const auto& range: block.except_ranges)
            if (range.first <= lineNo && lineNo <= range.second) return true;
    return false;
}
\n//=============================================================================\n''')
        text = text.replace('(it->end_except_lineno < lineNo) && (it->end_lineno >= lineNo)',
                            '(it->finally_lineno > 0) && (it->finally_lineno <= lineNo) && (it->finally_end_lineno >= lineNo)')
        text = text.replace('(it->try_lineno < lineNo) && (it->except_lineno > lineNo)',
                            '(it->body_lineno <= lineNo) && (it->end_try_lineno >= lineNo)')
    elif name.endswith('SPELLvariableMonitor.C'):
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
        text = text.replace('#include "Python-ast.h"', '#include "SPELL_UTIL/SPELLpython313.H"\n#include "SPELL_UTIL/SPELLanalysis313.H"\n#include <memory>')
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
        text = section(text, 'PyFrameObject* SPELLpythonHelper::createFrame(',
                       'void SPELLpythonHelper::checkError()', body('helper_frames.cpp'))
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
        # These setters deliberately leave a Python exception for a C callback
        # to return. A checking monitor consumed it before the caller saw it.
        text = text.replace('SPELLsafePythonOperations ops("terminate");', 'SPELLpython313::GIL ops;')
        text = text.replace('SPELLsafePythonOperations ops("SPELLerror::executionTerminated");', 'SPELLpython313::GIL ops;')
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
    bridge = source/'include/SPELL_UTIL/SPELLanalysis313.H'
    bridge.write_bytes((ROOT/bridge.name).read_bytes())
    embedded = source/'include/SPELL_UTIL/SPELLanalysisSource.H'
    support = body('analysis_support.py')
    assert ')SPELL_ANALYSIS"' not in support
    embedded.write_text('// SPDX-License-Identifier: GPL-3.0-or-later\nstatic const char analysisSource[] = R"SPELL_ANALYSIS(' + support + ')SPELL_ANALYSIS";\n',encoding='utf-8')
    for path in (bridge, embedded):
        changed[path.relative_to(source).as_posix()] = {'new':True,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    return changed
