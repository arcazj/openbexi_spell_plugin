// SPDX-License-Identifier: GPL-3.0-or-later
// Upstream accepts both full and residual microseconds alongside milliseconds.
// Use the same fractional representation as getMicrosecondsSuffix().
SPELLtime SPELLtime::operator+(const SPELLtime& other)
{
    const unsigned long fraction=static_cast<unsigned long>(m_msecs)*1000 + m_usecs%1000
        + static_cast<unsigned long>(other.m_msecs)*1000 + other.m_usecs%1000;
    const unsigned long carry=fraction/1000000;
    const auto maximum=std::numeric_limits<unsigned long>::max();
    if (other.m_secs>maximum-m_secs || carry>maximum-m_secs-other.m_secs)
        throw std::overflow_error("Native SPELL time addition overflow");
    return SPELLtime(m_secs+other.m_secs+carry,(fraction%1000000)/1000,
                     fraction%1000,m_delta && other.m_delta);
}

SPELLtime& SPELLtime::operator+=(SPELLtime& other)
{
    *this=*this+other; return *this;
}

SPELLtime SPELLtime::operator-(const SPELLtime& other)
{
    const bool delta=m_delta==other.m_delta;
    const unsigned long left=static_cast<unsigned long>(m_msecs)*1000+m_usecs%1000;
    const unsigned long right=static_cast<unsigned long>(other.m_msecs)*1000+other.m_usecs%1000;
    // Preserve the original unsigned-time contract: differences below zero
    // saturate at zero, including the fractional part.
    if (m_secs<other.m_secs || (m_secs==other.m_secs && left<right))
        return SPELLtime(0,0,0,delta);
    unsigned long seconds=m_secs-other.m_secs;
    unsigned long fraction;
    if (left<right) { --seconds;fraction=1000000+left-right; }
    else fraction=left-right;
    return SPELLtime(seconds,fraction/1000,fraction%1000,delta);
}

SPELLtime& SPELLtime::operator-=(SPELLtime& other)
{
    *this=*this-other; return *this;
}

