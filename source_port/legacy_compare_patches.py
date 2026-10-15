"""Experimental exact-preimage bridge for the documented legacy <> token.

SPDX-License-Identifier: GPL-3.0-or-later
Not part of the composed runtime until native acceptance evidence is complete.
"""
import hashlib
import json
from pathlib import Path

PREIMAGES = {
    'lib/SPELL_UTIL/src/SPELLpythonHelper.C': (
        '2610cab71f4d339ff33ffaa90486deaa060cf3060435a433b8f888c72824d837',
        '408e67f082a8b9ccdf0b13d9d8d905f49bb7c4402ea1b50cdf16f571d1069d02'),
    'lib/SPELL_EXC/src/SPELLastAnalyzer.C': (
        '5f5ab545c54e182c5b4b74feaae7ee386bb5d926f85b066dfe38b5ad73de59af',
        '57c83b92019fb31adfa1e81c670fda3f883b25d0fc6371c0ef7abda063814519'),
}


def bridge():
    syntax = Path(__file__).with_name('legacy_compare_syntax.py').read_text(encoding='utf-8')
    return r'''
// Recognize only the complete legacy operator token. Source locations and
// ordinary Python strings/comments remain unchanged; no builtin is replaced.
static std::string spellLegacyComparison(const std::string& source)
{
    if (source.find("<>") == std::string::npos) return source;
    SPELLpython313::GIL gil;
    using SPELLpython313::Owned;
    auto& helper = SPELLpythonHelper::instance();
    Owned environment(PyDict_New());
    if (!environment.get()) helper.checkError();
    if (PyDict_SetItemString(environment.get(), "__builtins__", PyEval_GetBuiltins()) < 0)
        helper.checkError();
    Owned loaded(PyRun_String(SYNTAX_SOURCE, Py_file_input, environment.get(), environment.get()));
    if (!loaded.get()) helper.checkError();
    Owned bytes(PyBytes_FromStringAndSize(source.data(), source.size()));
    if (!bytes.get()) helper.checkError();
    PyObject* normalize = PyDict_GetItemString(environment.get(), "normalize");
    if (!normalize) {
        PyErr_SetString(PyExc_RuntimeError, "Legacy comparison normalizer missing");
        helper.checkError();
    }
    Owned result(PyObject_CallOneArg(normalize, bytes.get()));
    if (!result.get()) helper.checkError();
    char* data = nullptr;
    Py_ssize_t size = 0;
    if (PyBytes_AsStringAndSize(result.get(), &data, &size) < 0) helper.checkError();
    return std::string(data, static_cast<size_t>(size));
}

'''.replace('SYNTAX_SOURCE', json.dumps(syntax, ensure_ascii=True))


def apply(name, original, ported):
    if name not in PREIMAGES or tuple(hashlib.sha256(raw).hexdigest() for raw in (original, ported)) != PREIMAGES[name]:
        raise ValueError('Legacy comparison preimage differs: ' + name)
    text = ported.decode('utf-8')
    if name.endswith('SPELLpythonHelper.C'):
        start = text.index('PyCodeObject* SPELLpythonHelper::compile(')
        end = text.index('bool SPELLpythonHelper::setNewLine(', start)
        block = text[start:end]
        before = '    PyCompilerFlags flags = {};'
        assert block.count(before) == 2
        block = block.replace(before, '    const std::string compatible = spellLegacyComparison(source);\n' + before)
        assert block.count('source.c_str()') == 2 and block.count('remember(code, source)') == 2
        block = block.replace('source.c_str()', 'compatible.c_str()').replace('remember(code, source)', 'remember(code, compatible)')
        text = text[:start] + bridge() + block + text[end:]
    else:
        start = text.index('void SPELLastAnalyzer::process(')
        before = '    PyCompilerFlags flags{};'
        assert text.count(before) == 1
        text = text[:start] + bridge() + text[start:]
        text = text.replace(before, '    source = spellLegacyComparison(source);\n' + before)
    return text.encode('utf-8')
