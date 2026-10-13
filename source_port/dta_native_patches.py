"""Checked original DTA declaration, prompt conversion and display corrections.

SPDX-License-Identifier: GPL-3.0-or-later
Applies after the established CPython port; no native type is substituted.
"""
import hashlib

SOURCE = 'lib/SPELL_DTA/src/SPELLdtaVariable.C'
ORIGINAL = '1fc250c12a0e5dce65471c8a9fa4b4a31fc377bb77e8dce8aeddeebb0b60913e'
PORTED = '28e8dcc1a1478438beade24dfbade95e6b29b24dcaca3dc0f65b998838950f3e'


def apply(name, original, ported):
    if (name != SOURCE or hashlib.sha256(original).hexdigest() != ORIGINAL
            or hashlib.sha256(ported).hexdigest() != PORTED):
        raise ValueError('Unexpected original or ported DTA variable source')
    text = ported.decode('utf-8')

    def replace(before, after, count=1):
        nonlocal text
        if text.count(before) != count:
            raise ValueError('Unexpected DTA source block: ' + before)
        text = text.replace(before, after)

    replace('#include "SPELL_UTIL/SPELLpython313.H"', '#include "SPELL_UTIL/SPELLpython313.H"\n#include <charconv>')

    helpers = '''namespace {
PyObject* dataTimeLiteral(const std::string& value)
{
    SPELLpython313::Owned module(PyImport_ImportModule("spell.lib.adapter.utctime"));
    if (!module.get()) SPELLpythonHelper::instance().checkError();
    SPELLpython313::Owned type(PyObject_GetAttrString(module.get(), "TIME"));
    SPELLpython313::Owned input(PyUnicode_FromStringAndSize(value.data(), value.size()));
    if (!type.get() || !input.get()) SPELLpythonHelper::instance().checkError();
    PyObject* result = PyObject_CallOneArg(type.get(), input.get());
    if (!result) SPELLpythonHelper::instance().checkError();
    return result;
}

PyObject* dataLiteral(const std::string& value)
{
    SPELLpython313::Owned module(PyImport_ImportModule("ast"));
    if (!module.get()) SPELLpythonHelper::instance().checkError();
    SPELLpython313::Owned parse(PyObject_GetAttrString(module.get(), "literal_eval"));
    SPELLpython313::Owned input(PyUnicode_FromStringAndSize(value.data(), value.size()));
    if (!parse.get() || !input.get()) SPELLpythonHelper::instance().checkError();
    PyObject* result = PyObject_CallOneArg(parse.get(), input.get());
    if (!result) SPELLpythonHelper::instance().checkError();
    return result;
}
}

'''
    marker = '//============================================================================\n// CONSTRUCTOR: SPELLdtaVariable::SPELLdtaVariable'
    replace(marker, helpers + marker)
    replace('''\t\t\tgetGivenValue(kwds);
\t\t\tgetGivenRange(kwds);
\t\t\tgetGivenExpected(kwds);
\t\t\tgetGivenConfirm(kwds);''', '''            getGivenValue(kwds);
            getGivenType(kwds); // Range/Expected TIME conversion requires the declared type.
            getGivenRange(kwds);
            getGivenExpected(kwds);
            getGivenConfirm(kwds);
            if (!m_range.empty() && !m_expected.empty())
                THROW_EXCEPTION("Cannot create variable container", "Range and Expected cannot be combined", SPELL_ERROR_LANGUAGE);''')
    replace('''\t\tint numExpected = PyList_Size(expected);''', '''        if (expected == Py_None) return;
        int numExpected = PyList_Size(expected);''')
    replace('''\t\tfor(int idx = 0; idx < 2; idx++)''', '''        if (range == Py_None) return;
        for(int idx = 0; idx < 2; idx++)''')
    replace('''\t\tm_format = PYSSTR(format);''', '''        m_format = PYSSTR(format);
        if (m_format != LanguageConstants::OCT && m_format != LanguageConstants::BIN &&
            m_format != LanguageConstants::HEX && m_format != LanguageConstants::DEC)
            THROW_EXCEPTION("Cannot create variable container", "Expected HEX, BIN, OCT or DEC format", SPELL_ERROR_LANGUAGE);''')
    replace('''void SPELLdtaVariable::checkRangeConsistent()
{''', '''void SPELLdtaVariable::checkRangeConsistent()
{
    if (!m_range.empty() && m_type == LanguageConstants::STRING)
        THROW_EXCEPTION("Cannot create variable container", "STRING variables cannot have a Range", SPELL_ERROR_LANGUAGE);
    if (!m_range.empty() && m_range[0] > m_range[1])
        THROW_EXCEPTION("Cannot create variable container", "Range lower limit exceeds upper limit", SPELL_ERROR_LANGUAGE);''')

    start = text.index('std::string SPELLdtaVariable::formatValue(')
    end = text.index('//============================================================================', start)
    text = text[:start] + '''std::string SPELLdtaVariable::formatValue( SPELLpyValue& value )
{
    if (m_type != LanguageConstants::LONG || value.typeStr() != LanguageConstants::LONG)
        return value.str();
    const char* specification = nullptr;
    if (m_format == LanguageConstants::BIN) specification = "b";
    else if (m_format == LanguageConstants::HEX) specification = "X";
    else if (m_format == LanguageConstants::OCT) specification = "o";
    if (!specification) return value.str();
    SPELLpython313::Owned number(value.get());
    SPELLpython313::Owned format(PyUnicode_FromString(specification));
    if (!number.get() || !format.get()) SPELLpythonHelper::instance().checkError();
    SPELLpython313::Owned rendered(PyObject_Format(number.get(), format.get()));
    if (!rendered.get()) SPELLpythonHelper::instance().checkError();
    std::string digits = PYSSTR(rendered.get());
    std::string prefix = m_format == LanguageConstants::BIN ? "0b" : m_format == LanguageConstants::HEX ? "0x" : "0";
    return digits[0] == '-' ? "-" + prefix + digits.substr(1) : prefix + digits;
}

''' + text[end:]
    replace('''\t\t\tvalue = SPELLpythonHelper::instance().pythonTime( value.str() );''', '''            SPELLpython313::Owned converted(dataTimeLiteral(value.str()));
            value = converted.get();''')
    replace('''\t\t\t\tSPELLpyValue newExp = SPELLpythonHelper::instance().pythonTime( exp.str() );''', '''                SPELLpython313::Owned converted(dataTimeLiteral(exp.str()));
                SPELLpyValue newExp = converted.get();''')
    replace('''\t\t\tSPELLpyValue newLo = SPELLpythonHelper::instance().pythonTime( lo.str() );''', '''            SPELLpython313::Owned convertedLo(dataTimeLiteral(lo.str()));
            SPELLpyValue newLo = convertedLo.get();''')
    replace('''\t\t\tSPELLpyValue newHi = SPELLpythonHelper::instance().pythonTime( hi.str() );''', '''            SPELLpython313::Owned convertedHi(dataTimeLiteral(hi.str()));
            SPELLpyValue newHi = convertedHi.get();''')
    replace('''\tif (!m_expected.empty())
\t{
\t\tpromptDef.typecode = LanguageConstants::PROMPT_LIST | LanguageConstants::PROMPT_ALPHA;''', '''    if (!m_expected.empty())
    {
        // Select the already typed Expected value by index; never re-evaluate its display text.
        promptDef.typecode = LanguageConstants::PROMPT_LIST | LanguageConstants::PROMPT_NUM;''')
    start = text.index('''\t\t\tif (m_type == LanguageConstants::DATETIME || m_type == LanguageConstants::RELTIME)''', text.index('bool SPELLdtaVariable::promptForValue('))
    end = text.index('''\t\t\treturn true;''', start)
    text = text[:start] + '''            SPELLpython313::Owned value;
            if (!m_expected.empty())
            {
                int index = -1;
                auto parsed = std::from_chars(answer.data(), answer.data()+answer.size(), index);
                if (parsed.ec != std::errc() || parsed.ptr != answer.data()+answer.size() ||
                    index < 0 || static_cast<size_t>(index) >= m_expected.size())
                    THROW_EXCEPTION("Cannot accept value", "Invalid expected-value index", SPELL_ERROR_LANGUAGE);
                value.reset(m_expected[index].get());
            }
            else if (m_type == LanguageConstants::DATETIME || m_type == LanguageConstants::RELTIME)
            {
                value.reset(dataTimeLiteral(answer));
            }
            else if (m_type == LanguageConstants::STRING)
            {
                SPELLutils::trim(answer);
                if (!answer.empty() && (answer[0] == '\\'' || answer[0] == '"'))
                    value.reset(dataLiteral(answer));
                else
                    value.reset(PyUnicode_FromStringAndSize(answer.data(), answer.size()));
            }
            else
            {
                value.reset(dataLiteral(answer));
            }
            if (!value.get()) SPELLpythonHelper::instance().checkError();
            setValue(value.get());
''' + text[end:]
    replace('''\t\tPy_INCREF(Py_None);''', '''        // Py_None is represented by value, without an owned Python reference.''')
    replace('''\t\tm_value = value;''', '''        // A format declared before type inference still requires an integer.
        // Validate before storing/inferencing so a rejected value leaves the variable unset.
        if (!value.isNone() && m_type.empty() && !m_format.empty() &&
            value.typeStr() != LanguageConstants::LONG)
            THROW_EXCEPTION("Cannot accept value", "Given format requires a LONG value", SPELL_ERROR_LANGUAGE);
        m_value = value;''')
    return text.encode('utf-8')
