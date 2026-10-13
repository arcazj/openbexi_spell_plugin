"""Narrow original-source CIF prompt fixes for native v0.5 conformance.

SPDX-License-Identifier: GPL-3.0-or-later
Applied after the established CPython 3.13 port; accepted recipes stay intact.
"""
import hashlib

SOURCE = 'lib/SPELL_CIF/src/SPELLcifHelper.C'
PREIMAGE = '7316ec1d703e4aa883adbb07301ea7428b3fb111460bf4cfe3b3e7c974018a24'
PORTED = 'a70ddb9c485ce730b9adc62b952a1f89ed31fac491ebcbb2ef8e602c70c5579c'


def apply(name, original, ported):
    if (name != SOURCE or hashlib.sha256(original).hexdigest() != PREIMAGE
            or hashlib.sha256(ported).hexdigest() != PORTED):
        raise ValueError('Unexpected original CIF prompt source')
    text = ported.decode('utf-8')

    def replace(before, after, count=1):
        nonlocal text
        if text.count(before) != count:
            raise ValueError('Unexpected ported CIF prompt source: ' + before)
        text = text.replace(before, after)

    replace('#include "SPELL_CIF/SPELLcifHelper.H"',
            '#include "SPELL_CIF/SPELLcifHelper.H"\n#include "SPELL_UTIL/SPELLpython313.H"')
    # These conversions return new references and never evaluate prompt input.
    # PyFloat_FromString borrows its string argument, so retain that temporary
    # until conversion finishes, on both successful and failed conversions.
    conversions = '''namespace {
PyObject* promptNumericResult(const std::string& answer)
{
    PyObject* integer = PyLong_FromString(const_cast<char*>(answer.c_str()), nullptr, 0);
    if (integer) return integer;
    if (!PyErr_ExceptionMatches(PyExc_ValueError)) return nullptr;
    PyErr_Clear();
    SPELLpython313::Owned text(PyUnicode_FromStringAndSize(answer.data(), answer.size()));
    if (!text.get()) return nullptr;
    // The upstream CPython-3 macro removes the obsolete second argument.
    return PyFloat_FromString(text.get(), nullptr);
}

PyObject* promptDateResult(const std::string& answer)
{
    SPELLpython313::Owned module(PyImport_ImportModule("spell.lib.adapter.utctime"));
    if (!module.get()) return nullptr;
    SPELLpython313::Owned type(PyObject_GetAttrString(module.get(), "TIME"));
    SPELLpython313::Owned text(PyUnicode_FromStringAndSize(answer.data(), answer.size()));
    if (!type.get() || !text.get()) return nullptr;
    SPELLpython313::Owned value(PyObject_CallOneArg(type.get(), text.get()));
    if (!value.get()) return nullptr;
    SPELLpython313::Owned absolute(PyObject_CallMethod(value.get(), "isAbs", nullptr));
    if (!absolute.get()) return nullptr;
    int isAbsolute = PyObject_IsTrue(absolute.get());
    if (isAbsolute < 0) return nullptr;
    if (!isAbsolute)
    {
        PyErr_SetString(PyExc_ValueError, "DATE requires an absolute date, not a relative duration");
        return nullptr;
    }
    return Py_NewRef(value.get());
}
}

'''
    signature = 'PyObject* SPELLcifHelper::getPythonResult( const std::string& result, const SPELLpromptDefinition& def )'
    replace(signature, conversions + signature)

    # Keep the original switch and failure policy; replace both duplicated
    # numeric-parser blocks with an integer-first, full float-grammar converter.
    # This includes 1e3/1E3, which the original punctuation heuristic rejected.
    start = text.index(signature)
    end = text.index('std::string SPELLcifHelper::getResult(', start)
    body = text[start:end]
    import re
    numeric_pattern = r'\s*if \(\(result\.find\("\."\).*?promptResult = PyLong_FromString\( const_cast<char\*>\(result\.c_str\(\)\), NULL, 0 \);\s*\}'
    body, count = re.subn(numeric_pattern, '\n            promptResult = promptNumericResult(result);', body, flags=re.S)
    if count != 2:
        raise ValueError('Expected two original numeric conversion blocks')
    text = text[:start] + body + text[end:]

    date_before = '''        \ttry
        \t{
        \t\tpromptResult = SPELLpythonHelper::instance().pythonTime(result);
        \t}
        \tcatch(SPELLcoreException& ex)
        \t{
        \t\tTHROW_DRIVER_EXCEPTION("Error on prompt", "Unable to format answer to SPELL date");
        \t}'''
    replace(date_before, '''            promptResult = promptDateResult(result);
            if (!promptResult)
            {
                PyErr_Clear();
                THROW_DRIVER_EXCEPTION("Error on prompt", "Unable to format answer to an absolute SPELL date");
            }''')

    # All custom-list answers arrive as zero-based wire indices. Reject malformed
    # or overflowing answers before reading an option; atoi silently accepted
    # strings such as "bad", "1junk" and "1.5".
    replace('''        \tint optionIndex = STRI(result);
        \tif (optionIndex < 0 || (unsigned)optionIndex >= def.options.size()){
        \t\treturn "";
        \t}''', '''            int optionIndex = -1;
            auto conversion = std::from_chars(result.data(), result.data()+result.size(), optionIndex);
            if (conversion.ec != std::errc() || conversion.ptr != result.data()+result.size() ||
                optionIndex < 0 || static_cast<size_t>(optionIndex) >= def.options.size())
                THROW_EXCEPTION("Invalid prompt answer", "Answer is not a valid option index", SPELL_ERROR_EXECUTION);''')
    alpha_start = text.index('        \t// Conversion LIST|ALPHA')
    alpha_end = text.index('        \t// Conversion LIST|NUM', alpha_start)
    text = text[:alpha_start] + '''            // LIST|ALPHA returns the selected value, including keyed options.
            if ((def.typecode & LanguageConstants::PROMPT_ALPHA) > 0)
            {
                promptResult = def.options[optionIndex];
                auto separator = promptResult.find(":");
                if (separator != std::string::npos)
                {
                    promptResult = promptResult.substr(separator+1);
                    SPELLutils::trim(promptResult);
                }
            }
''' + text[alpha_end:]

    # LRM 2.4.4 p.71 Example116 explicitly returns option indices 0 or 1.
    # The wire also uses zero-based indices; do not add one to the return value.
    replace('promptResult = ISTR(STRI(result) + 1); // index correction',
            'promptResult = ISTR(optionIndex); // LRM zero-based option index')
    # Failed CPython conversions set an error. Clear it before constructing a
    # SPELL DriverException, whose import and constructor require a clean state.
    replace('THROW_DRIVER_EXCEPTION("Error on prompt", "Unable to format answer to numeric value");',
            'PyErr_Clear();\n                THROW_DRIVER_EXCEPTION("Error on prompt", "Unable to format answer to numeric value");')
    replace('THROW_DRIVER_EXCEPTION("Error on prompt", "Unable to get answer");',
            'PyErr_Clear();\n            THROW_DRIVER_EXCEPTION("Error on prompt", "Unable to get answer");')
    # Every successful branch above returns a new reference. Do not leak it by
    # adding another reference before returning to the Python binding.
    replace('        \tPy_INCREF(promptResult);',
            '            // promptResult is already a new CPython reference.')
    return text.encode('utf-8')
