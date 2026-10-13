"""Checked native FLOW corrections; apply after the accepted CPython port.

Preserves upstream notices. SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
from pathlib import Path

PREIMAGES = {
    'lib/SPELL_CIF/src/SPELLasRun.C': '1ecc3fd84a1d68131eed7f22e521f5494488a4e534787e16eefd0461e89c734a',
    'lib/SPELL_EXC/src/SPELLgoto.C': 'e11ed91568be4b4874b00677ce387e511f58bef960a7ead8195e4e5be22da7a7',
}


def apply_tree(source, output=None):
    source = Path(source)
    report = {}
    helper = Path(__file__).with_name('flow_analyze.py').read_text(encoding='utf-8')
    for name, expected in PREIMAGES.items():
        path = source / name
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected, name
        text = raw.decode()
        if name.endswith('SPELLasRun.C'):
            old = 'SEVERITY_STR[severity]'
            assert text.count(old) == 1
            text = text.replace(old, '(severity == LanguageConstants::INFORMATION ? SEVERITY_STR[0] : '
                                'severity == LanguageConstants::WARNING ? SEVERITY_STR[1] : '
                                'severity == LanguageConstants::ERROR ? SEVERITY_STR[2] : STR("UNKNOWN"))')
        else:
            start = text.index('void SPELLgoto::analyze()')
            end = text.index('std::string SPELLgoto::validateGotos()', start)
            replacement = r'''void SPELLgoto::analyze()
{
    SPELLpython313::GIL gil;
    using SPELLpython313::Owned;
    auto& helper = SPELLpythonHelper::instance();
    m_initLine = -1;
    Owned environment(PyDict_New());
    if (!environment.get()) helper.checkError();
    if (PyDict_SetItemString(environment.get(), "__builtins__", PyEval_GetBuiltins()) < 0)
        helper.checkError();
    const char* analysisSource = ANALYSIS_SOURCE;
    Owned loaded(PyRun_String(analysisSource, Py_file_input, environment.get(), environment.get()));
    if (!loaded.get()) helper.checkError();
    PyObject* function = PyDict_GetItemString(environment.get(), "analyze_flow");
    Owned labels(PyObject_CallOneArg(function, reinterpret_cast<PyObject*>(m_code)));
    if (!labels.get()) helper.checkError();
    for (Py_ssize_t index = 0; index < PyList_GET_SIZE(labels.get()); ++index) {
        PyObject* row = PyList_GET_ITEM(labels.get(), index);
        std::string kind = SPELLpython313::text(PyTuple_GET_ITEM(row, 0));
        std::string label = SPELLpython313::text(PyTuple_GET_ITEM(row, 1));
        PyObject* title = PyTuple_GET_ITEM(row, 2);
        long offset = PyLong_AsLong(PyTuple_GET_ITEM(row, 3));
        helper.checkError();
        int line = PyCode_Addr2Line(m_code, offset);
        if (line <= 0) continue;
        if (kind == "Step") {
            m_labels.insert(std::make_pair(label, line));
            m_labelLines.insert(line);
            if (title != Py_None)
                m_titles.insert(std::make_pair(SPELLpython313::text(title), label));
            if (label == "INIT") m_initLine = line;
        } else {
            m_gotos.insert(std::make_pair(line, label));
        }
    }
    helper.checkError();
}

//=============================================================================
'''
            # JSON string escaping is valid C++ string literal escaping here;
            # ensure_ascii keeps the embedded source independent of locale.
            replacement = replacement.replace('ANALYSIS_SOURCE', json.dumps(helper, ensure_ascii=True))
            text = text[:start] + replacement + text[end:]
        path.write_bytes(text.encode())
        report[name] = {'preimage_sha256': expected, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    if output:
        Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


PYTHON_PREIMAGE = 'ed1996d406a999f832a0a1e83039f619cf99f1901a9f4f4eab9492944549814d'


def apply_python_tree(site, output=None):
    """Validate public user-action arguments before any native state mutation."""
    path = Path(site) / 'spell/lang/helpers/exechelper.py'
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PYTHON_PREIMAGE, str(path)
    text = raw.decode()
    start = text.index('class SetUserAction_Helper')
    end = text.index('class EnableUserAction_Helper', start)
    block = text[start:end]
    assert block.count('if len(args)<2:') == 1
    block = block.replace('if len(args)<2:', 'if len(args)!=2:')
    marker = '        self.__function = args[0]'
    assert block.count(marker) == 1
    block = block.replace(marker, '''        severity = self.getConfig().get(Severity, INFORMATION)
        if type(severity) is not int or severity not in (INFORMATION, WARNING, ERROR):
            raise SyntaxException("Expected INFORMATION, WARNING or ERROR severity")

''' + marker)
    text = text[:start] + block + text[end:]
    for name in ('EnableUserAction', 'DisableUserAction', 'DismissUserAction'):
        start = text.index('class ' + name + '_Helper')
        marker = '    def _doOperation(self, *args, **kargs ):'
        position = text.index(marker, start)
        preoperation = '''    def _doPreOperation(self, *args, **kargs):
        if args:
            raise SyntaxException("''' + name + ''' takes no positional arguments")

    #===========================================================================
'''
        text = text[:position] + preoperation + text[position:]
    path.write_bytes(text.encode())
    report = {'spell/lang/helpers/exechelper.py': {
        'preimage_sha256': PYTHON_PREIMAGE,
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
    if output:
        Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report
