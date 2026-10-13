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
        body = text[begin:end]
        old = 'secs = PyLong_AsLong(pyDoub.get());'
        if body.count(old) != 2:
            raise ValueError('Unexpected native TIME float conversion')
        body = body.replace(old, old + '''
                // TIME.microsecond() is the positive fractional field from
                // datetime/timedelta. Use floor seconds, including before epoch.
                if (fsecs < 0.0 && usecs != 0) --secs;''')
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
    text = text[:begin] + body + text[end:]
    # The original ABI stores seconds as unsigned long, including two's-complement
    # values supplied by evalTime. Interpret their signed value when comparing.
    for operation in ('<', '>', '<=', '>='):
        old = 'm_secs ' + operation + ' other.m_secs'
        text = text.replace(old, 'static_cast<long>(m_secs) ' + operation + ' static_cast<long>(other.m_secs)')
    return text.encode('utf-8')
