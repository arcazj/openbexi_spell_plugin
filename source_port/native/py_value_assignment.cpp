// SPDX-License-Identifier: GPL-3.0-or-later
SPELLpyValue& SPELLpyValue::operator=(const SPELLpyValue& other)
{
    if (this == &other) return *this;
    m_intValue = other.m_intValue;
    m_floatValue = other.m_floatValue;
    m_boolValue = other.m_boolValue;
    m_stringValue = other.m_stringValue;
    m_timeValue = other.m_timeValue;
    m_type = other.m_type;
    m_listValue = other.m_listValue;
    m_dictValue = other.m_dictValue;
    return *this;
}
