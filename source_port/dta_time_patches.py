"""Checked native TIME value boundaries used by original DTA variables.

SPDX-License-Identifier: GPL-3.0-or-later
Preserves the original native layout and fixes its textual round trip at epoch
zero and for negative durations, including normalized fractional seconds.
"""
import hashlib

PREIMAGES = {
    'lib/SPELL_UTIL/src/SPELLtime.C': (
        '00eee7607928a34af2ba69a687b290566687155a80d7299d9a4a1f432f248585',
        '51125a81fbe7e674376de71af7bc6eeb25f06d8be35f6425e658d508ba5394f8'),
    'lib/SPELL_UTIL/src/SPELLpythonHelper.C': (
        '2610cab71f4d339ff33ffaa90486deaa060cf3060435a433b8f888c72824d837',
        '408e67f082a8b9ccdf0b13d9d8d905f49bb7c4402ea1b50cdf16f571d1069d02'),
}


def apply(name, original, ported):
    expected = PREIMAGES.get(name)
    if not expected or (hashlib.sha256(original).hexdigest(), hashlib.sha256(ported).hexdigest()) != expected:
        raise ValueError('Unexpected original or ported native TIME source: ' + name)
    text = ported.decode('utf-8')
    if name.endswith('SPELLpythonHelper.C'):
        begin = text.index('SPELLtime SPELLpythonHelper::evalTime( PyObject* expression )')
        end = text.index('SPELLtime SPELLpythonHelper::evalTime( const std::string& expression )', begin)
        body = '''SPELLtime SPELLpythonHelper::evalTime( PyObject* expression )
{
    if (!isTime(expression)) return evalTime(PYSSTR(expression));
    // Resolve NOW and other dynamic TIME values exactly once. Float abs()/rel()
    // round fractional values at large dates/durations and can change seconds.
    SPELLpython313::Owned value(callMethod(expression, "value", NULL));
    if (!value.get()) checkError();
    SPELLpython313::Owned relative(callMethod(expression, "isRel", NULL));
    if (!relative.get()) checkError();
    const int isRelative = PyObject_IsTrue(relative.get());
    if (isRelative < 0) checkError();
    SPELLpython313::Owned whole;
    if (isRelative)
    {
        SPELLpython313::Owned days(PyObject_GetAttrString(value.get(), "days"));
        SPELLpython313::Owned seconds(PyObject_GetAttrString(value.get(), "seconds"));
        SPELLpython313::Owned perDay(PyLong_FromLong(86400));
        if (!days.get() || !seconds.get() || !perDay.get()) checkError();
        SPELLpython313::Owned daySeconds(PyNumber_Multiply(days.get(), perDay.get()));
        if (!daySeconds.get()) checkError();
        whole.reset(PyNumber_Add(daySeconds.get(), seconds.get()));
    }
    else
    {
        SPELLpython313::Owned calendar(PyImport_ImportModule("calendar"));
        if (!calendar.get()) checkError();
        SPELLpython313::Owned timegm(PyObject_GetAttrString(calendar.get(), "timegm"));
        SPELLpython313::Owned fields(PyObject_CallMethod(value.get(), "utctimetuple", NULL));
        if (!timegm.get() || !fields.get()) checkError();
        whole.reset(PyObject_CallOneArg(timegm.get(), fields.get()));
    }
    if (!whole.get()) checkError();
    const long seconds = PyLong_AsLong(whole.get());
    if (PyErr_Occurred()) checkError();
    SPELLpython313::Owned fraction(PyObject_GetAttrString(value.get(),
        isRelative ? "microseconds" : "microsecond"));
    if (!fraction.get()) checkError();
    const unsigned long micros = PyLong_AsUnsignedLong(fraction.get());
    if (PyErr_Occurred()) checkError();
    if (micros >= 1000000)
        THROW_EXCEPTION("Invalid TIME value", "Microseconds out of range", SPELL_ERROR_LANGUAGE);
    return SPELLtime(seconds, micros / 1000, micros % 1000, isRelative != 0);
}

'''
        return (text[:begin] + body + text[end:]).encode('utf-8')

    old = 'if (m_secs==0 && m_msecs==0 && m_usecs==0)'
    begin = text.index('std::string SPELLtime::toTIMEString() const')
    end = text.index('void SPELLtime::setCurrent()', begin)
    body = text[begin:end]
    if body.count(old) != 1:
        raise ValueError('Unexpected native TIME zero conversion')
    body = body.replace(old, 'if (isDelta() && m_secs==0 && m_msecs==0 && m_usecs==0)')
    relative_begin = body.index('''    if (isDelta())
    {''')
    relative_end = body.index('''    //Absolute date''', relative_begin)
    body = body[:relative_begin] + '''    if (isDelta())
    {
        const long signedSeconds = static_cast<long>(m_secs);
        const bool negative = signedSeconds < 0;
        unsigned long seconds = negative ? static_cast<unsigned long>(-(signedSeconds + 1)) + 1 : m_secs;
        unsigned int micros = m_msecs * 1000 + m_usecs % 1000;
        if (negative && micros)
        {
            --seconds;
            micros = 1000000 - micros;
        }
        std::ostringstream output;
        output << (negative ? "-" : "+");
        if (seconds >= 86400)
        {
            output << std::setfill('0') << std::setw(3) << seconds / 86400 << " ";
            seconds %= 86400;
        }
        output << std::setfill('0') << std::setw(2) << seconds / 3600 << ":"
               << std::setw(2) << (seconds / 60) % 60 << ":"
               << std::setw(2) << seconds % 60;
        if (micros)
        {
            output << "." << std::setw(3) << micros / 1000;
            if (micros % 1000) output << std::setw(3) << micros % 1000;
        }
        return output.str();
    }
''' + body[relative_end:]
    body = body.replace('struct tm* ptm = localtime(&seconds);', 'struct tm* ptm = gmtime(&seconds);')
    body = body.replace('if (ptm==NULL && m_msecs==0 && m_usecs==0)', 'if (ptm==NULL)')
    old = 'timeStr += ISTR(1900+ptm->tm_year) + "-";'
    if body.count(old) != 1:
        raise ValueError('Unexpected native TIME year formatting')
    body = body.replace(old, '''std::ostringstream year;
        year << std::setfill('0') << std::setw(4) << 1900+ptm->tm_year;
        timeStr += year.str() + "-";''')
    text = text[:begin] + body + text[end:]
    # The original ABI stores seconds as unsigned long, including two's-complement
    # values supplied by evalTime. Interpret their signed value when comparing.
    for operation in ('<', '>', '<=', '>='):
        old = 'm_secs ' + operation + ' other.m_secs'
        text = text.replace(old, 'static_cast<long>(m_secs) ' + operation + ' static_cast<long>(other.m_secs)')
    return text.encode('utf-8')
