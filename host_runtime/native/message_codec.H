// SPDX-License-Identifier: GPL-3.0-or-later
// Included once by the checked private SPELLipcMessage.C composition.
// The class ABI and valid upstream wire format are unchanged.
#include <cstdint>
#include <limits>
#include <utility>
#include <algorithm>
#include <string_view>
#include <vector>
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
    std::string result;
    v08DataInto(result);
    return result;
}

void SPELLipcMessage::v08DataInto(std::string& result) const
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
    result.clear();
    // The socket layer prepends one compression byte. Reserve its space while
    // preserving the unframed data() API and its exact wire bytes.
    result.reserve(size + 1);
    for (const auto& field : metadata)
        v08_append_field(result, *field.first, *field.second);
    for (const auto& field : m_properties)
        v08_append_field(result, field.first, field.second);
}

void SPELLipcMessage::fromData(std::string data)
{
    v08FromData(data);
}

namespace {
struct V08FieldView {
    std::string_view name, value;
    size_t ordinal;
};
struct V08DecodeScratch {
    std::vector<V08FieldView> fields;
    std::string id, sender, receiver, key;
    bool busy=false;
};
// Input threads own their cache. A nested decode gets independent storage.
struct V08DecodeLease {
    V08DecodeScratch local;
    V08DecodeScratch& scratch;
    V08DecodeLease(V08DecodeScratch& cached):scratch(cached.busy ? local : cached) {
        scratch.busy=true;
    }
    ~V08DecodeLease() {
        scratch.fields.clear();
        if (scratch.fields.capacity()>4096)
            std::vector<V08FieldView>().swap(scratch.fields);
        for (auto* value:{&scratch.id,&scratch.sender,&scratch.receiver,&scratch.key}) {
            if (value->capacity()>1024*1024) std::string().swap(*value);
            else value->clear();
        }
        scratch.busy=false;
    }
};
}

void SPELLipcMessage::v08ReadData(std::string_view data)
{
    // Input dispatch used to construct a fresh message for every packet. Reset
    // every metadata member while retaining only the owned property storage.
    m_id="<void>"; m_sequence=-1; m_type=MSG_TYPE_NOTYPE;
    m_senderId=MessageId::GENERIC_ID; m_receiverId=MessageId::GENERIC_ID;
    m_compressed=DEFAULT_COMPRESSED_FLAG; m_key=-1;
    v08FromData(data);
}

void SPELLipcMessage::v08FromData(std::string_view data)
{
    static thread_local V08DecodeScratch cached;
    V08DecodeLease lease(cached);
    auto& fields=lease.scratch.fields;
    try {
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
            std::string_view value(data.data()+pos, size);
            pos += size;
            return value;
        };
        while (pos < data.size()) {
            auto name=take(length(2));
            auto value=take(length(4));
            fields.push_back({name,value,fields.size()});
        }
        std::sort(fields.begin(),fields.end(),[](const auto& a,const auto& b) {
            return a.name<b.name || (a.name==b.name && a.ordinal<b.ordinal);
        });
        auto& scratch=lease.scratch;
        auto& id=scratch.id; auto& sender=scratch.sender; auto& receiver=scratch.receiver;
        id=m_id; sender=m_senderId; receiver=m_receiverId;
        long sequence=m_sequence;
        int ipcKey=m_key;
        SPELLipcMessageType type=m_type;
        auto& key=scratch.key;
        for (size_t i=0;i<fields.size();++i) {
            const auto& field=fields[i];
            if (i+1<fields.size() && fields[i+1].name==field.name) continue;
            const auto name=field.name, value=field.value;
            // Last duplicate wins, exactly as in the frozen map decoder.
            if (name == MessageField::FIELD_ID) id.assign(value);
            else if (name == MessageField::FIELD_TYPE) type=StringToMessageType(std::string(value));
            else if (name == MessageField::FIELD_SENDER_ID) sender.assign(value);
            else if (name == MessageField::FIELD_RECEIVER_ID) receiver.assign(value);
            else if (name == MessageField::FIELD_SEQUENCE) sequence=STRI(std::string(value));
            else if (name == MessageField::FIELD_IPC_KEY) ipcKey=STRI(std::string(value));
            else {
                key.assign(name);
                m_properties[key].assign(value);
            }
        }
        for (auto it=m_properties.begin();it!=m_properties.end();) {
            const auto found=std::lower_bound(fields.begin(),fields.end(),std::string_view(it->first),
                [](const auto& field,std::string_view name) {return field.name<name;});
            const auto& name=it->first;
            const bool metadata=name==MessageField::FIELD_ID || name==MessageField::FIELD_TYPE
                || name==MessageField::FIELD_SENDER_ID || name==MessageField::FIELD_RECEIVER_ID
                || name==MessageField::FIELD_SEQUENCE || name==MessageField::FIELD_IPC_KEY;
            if (metadata || found==fields.end() || found->name!=name) it=m_properties.erase(it);
            else ++it;
        }
        m_id.swap(id); m_senderId.swap(sender); m_receiverId.swap(receiver);
        m_sequence=sequence; m_key=ipcKey; m_type=type;
    } catch (...) {
        // Preserve empty properties and unchanged metadata on malformed input.
        m_properties.clear();
        throw;
    }
}

#include "message_storage.H"
