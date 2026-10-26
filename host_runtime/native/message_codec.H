// SPDX-License-Identifier: GPL-3.0-or-later
// Included once by the checked private SPELLipcMessage.C composition.
// The class ABI and valid upstream wire format are unchanged.
#include <cstdint>
#include <limits>
#include <utility>
#include "SPELL_IPC/SPELLipcError.H"

namespace {
size_t v08_field_size(const std::string& key, const std::string& value)
{
    if (key.size() > UINT16_MAX || value.size() > UINT32_MAX)
        throw SPELLipcError("IPC field exceeds wire bounds", 0);
    return 6 + key.size() + value.size();
}

void v08_append_field(std::string& out, const std::string& key, const std::string& value)
{
    out.push_back(static_cast<char>(key.size() >> 8));
    out.push_back(static_cast<char>(key.size()));
    out.append(key);
    for (int shift : {24, 16, 8, 0})
        out.push_back(static_cast<char>(value.size() >> shift));
    out.append(value);
}
}

std::string SPELLipcMessage::data() const
{
    const std::string sequence = ISTR(m_sequence), key = ISTR(m_key);
    const std::pair<const std::string*, const std::string*> metadata[] = {
        {&MessageField::FIELD_SENDER_ID, &m_senderId},
        {&MessageField::FIELD_RECEIVER_ID, &m_receiverId},
        {&MessageField::FIELD_SEQUENCE, &sequence},
        {&MessageField::FIELD_ID, &m_id},
        {&MessageField::FIELD_TYPE, &MessageType::TypeStr[getType()]},
        {&MessageField::FIELD_IPC_KEY, &key},
    };
    size_t size = 0;
    auto account = [&](const std::string& name, const std::string& value) {
        const size_t field = v08_field_size(name, value);
        if (field > UINT32_MAX || size > UINT32_MAX - field)
            throw SPELLipcError("IPC message exceeds wire bounds", 0);
        size += field;
    };
    for (const auto& field : metadata) account(*field.first, *field.second);
    for (const auto& field : m_properties) account(field.first, field.second);
    std::string result;
    // The socket layer prepends one compression byte. Reserve its space while
    // preserving the unframed data() API and its exact wire bytes.
    result.reserve(size + 1);
    for (const auto& field : metadata)
        v08_append_field(result, *field.first, *field.second);
    for (const auto& field : m_properties)
        v08_append_field(result, field.first, field.second);
    return result;
}

void SPELLipcMessage::fromData(std::string data)
{
    v08FromData(data);
}

void SPELLipcMessage::v08FromData(const std::string& data)
{
    // The old decoder clears properties before parsing but does not mutate
    // metadata on a malformed packet. Preserve that failure behavior.
    m_properties.clear();
    Properties properties;
    std::string id=m_id, sender=m_senderId, receiver=m_receiverId;
    long sequence=m_sequence;
    int ipcKey=m_key;
    SPELLipcMessageType type=m_type;
    size_t pos=0;
    auto length = [&](unsigned width) {
        if (width > data.size()-pos)
            throw SPELLipcError("Truncated IPC field length", 0);
        uint32_t value=0;
        while (width--) value=(value << 8) | static_cast<unsigned char>(data[pos++]);
        return value;
    };
    auto take = [&](size_t size) {
        if (size > data.size()-pos)
            throw SPELLipcError("Truncated IPC field data", 0);
        std::string value(data.data()+pos, size);
        pos += size;
        return value;
    };
    while (pos < data.size()) {
        auto name=take(length(2));
        auto value=take(length(4));
        // Last duplicate wins, including metadata, just as the old map did.
        if (name == MessageField::FIELD_ID) id=std::move(value);
        else if (name == MessageField::FIELD_TYPE) type=StringToMessageType(value);
        else if (name == MessageField::FIELD_SENDER_ID) sender=std::move(value);
        else if (name == MessageField::FIELD_RECEIVER_ID) receiver=std::move(value);
        else if (name == MessageField::FIELD_SEQUENCE) sequence=STRI(value);
        else if (name == MessageField::FIELD_IPC_KEY) ipcKey=STRI(value);
        else properties[std::move(name)]=std::move(value);
    }
    m_id.swap(id); m_senderId.swap(sender); m_receiverId.swap(receiver);
    m_sequence=sequence; m_key=ipcKey; m_type=type;
    m_properties.swap(properties);
}
