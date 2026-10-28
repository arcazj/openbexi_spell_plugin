// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_BRIDGE_FRAME_H
#define OPENBEXI_V08_BRIDGE_FRAME_H

// One encoder per serialized output stream. Reuse JSON strings and the output
// buffer, never message ownership or acknowledgements. The JSON library still
// owns UTF-8 replacement, escaping, numeric formatting and key ordering.
class V08BridgeFrame {
    Json frame=Json::object();
    // Detached nodes remain exclusively owned by this encoder. They never
    // appear in a rendered frame until the current message contains that key.
    Json::object_t retiredFields, retiredHeaders;
    std::string bytes;
    nlohmann::detail::serializer<Json> serializer;

    static void text(Json& target, const std::string& value) {
        if (target.is_string()) target.get_ref<Json::string_t&>().assign(value);
        else target=value;
    }

    void retireHeader(const char* name) {
        auto& active=frame.get_ref<Json::object_t&>();
        const auto found=active.find(name);
        if (found!=active.end()) retiredHeaders.insert(active.extract(found));
    }

    Json& header(const char* name) {
        auto& active=frame.get_ref<Json::object_t&>();
        const auto found=active.find(name);
        if (found!=active.end()) return found->second;
        auto saved=retiredHeaders.extract(name);
        if (!saved.empty()) return active.insert(std::move(saved)).position->second;
        return frame[name];
    }

    void message(const SPELLipcMessage& source) {
        auto& target=frame["message"];
        if (!target.is_object()) target=Json::object();
        text(target["id"],source.getId()); target["type"]=source.getType();
        text(target["sender"],source.getSender());
        text(target["receiver"],source.getReceiver());
        auto& fields=target["fields"];
        if (!fields.is_object()) fields=Json::object();
        auto& active=fields.get_ref<Json::object_t&>();
        // Fields absent from this message must not leak from a prior frame.
        for (auto it=active.begin();it!=active.end();) {
            if (source.v08Fields().count(it->first)) { ++it; continue; }
            const auto absent=it++;
            // A bounded node cache covers alternating ordinary schemas. Large
            // values and excess keys follow normal destruction. No payload is
            // moved out of the measured process or out of sanitizer accounting.
            if (retiredFields.size()<64 && absent->first.capacity()<=128
                && absent->second.is_string()
                && absent->second.get_ref<const Json::string_t&>().capacity()<=4096)
                retiredFields.insert(active.extract(absent));
            else active.erase(absent);
        }
        for (const auto& field:source.v08Fields()) {
            if (std::find(std::begin(fieldNames),std::end(fieldNames),field.first)==std::end(fieldNames)) continue;
            auto found=active.find(field.first);
            if (found==active.end()) {
                auto saved=retiredFields.extract(field.first);
                if (!saved.empty()) found=active.insert(std::move(saved)).position;
            }
            if (found==active.end()) text(fields[field.first],field.second);
            else text(found->second,field.second);
        }
    }

    const std::string& render() {
        bytes.clear();
        serializer.dump(frame,false,false,0);
        return bytes;
    }

public:
    V08BridgeFrame():serializer(nlohmann::detail::output_adapter<char>(bytes),' ',
                               Json::error_handler_t::replace) {}
    V08BridgeFrame(const V08BridgeFrame&)=delete;
    V08BridgeFrame& operator=(const V08BridgeFrame&)=delete;

    const std::string& event(const char* name,const SPELLipcMessage& source) {
        retireHeader("seq");retireHeader("ok");
        text(header("event"),name);message(source);return render();
    }
    const std::string& reply(unsigned sequence,const SPELLipcMessage& source) {
        retireHeader("event");header("seq")=sequence;
        header("ok")=source.getType()!=MSG_TYPE_ERROR;
        message(source);return render();
    }
    void releaseLargeBuffers() {
        // Avoid retaining arbitrarily large previous payloads. The common
        // trace stream stays allocation-free after reaching its high water.
        if (bytes.capacity()>1024*1024) {
            std::string().swap(bytes);
            frame=Json::object();
            retiredFields.clear();retiredHeaders.clear();
        }
    }
};
#endif
