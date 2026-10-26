// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_BRIDGE_FRAME_H
#define OPENBEXI_V08_BRIDGE_FRAME_H

// One encoder per serialized output stream. Reuse JSON strings and the output
// buffer, never message ownership or acknowledgements. The JSON library still
// owns UTF-8 replacement, escaping, numeric formatting and key ordering.
class V08BridgeFrame {
    Json frame=Json::object();
    std::string bytes;
    nlohmann::detail::serializer<Json> serializer;

    static void text(Json& target, const std::string& value) {
        if (target.is_string()) target.get_ref<Json::string_t&>().assign(value);
        else target=value;
    }

    void message(const SPELLipcMessage& source) {
        auto& target=frame["message"];
        if (!target.is_object()) target=Json::object();
        text(target["id"],source.getId()); target["type"]=source.getType();
        text(target["sender"],source.getSender());
        text(target["receiver"],source.getReceiver());
        auto& fields=target["fields"];
        if (!fields.is_object()) fields=Json::object();
        // Fields absent from this message must not leak from a prior frame.
        for (auto it=fields.begin();it!=fields.end();) {
            if (!source.v08Fields().count(it.key())) it=fields.erase(it);
            else ++it;
        }
        for (const auto& field:source.v08Fields())
            if (std::find(std::begin(fieldNames),std::end(fieldNames),field.first)!=std::end(fieldNames))
                text(fields[field.first],field.second);
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
        frame.erase("seq");frame.erase("ok");
        text(frame["event"],name);message(source);return render();
    }
    const std::string& reply(unsigned sequence,const SPELLipcMessage& source) {
        frame.erase("event");frame["seq"]=sequence;
        frame["ok"]=source.getType()!=MSG_TYPE_ERROR;
        message(source);return render();
    }
    void releaseLargeBuffers() {
        // Avoid retaining arbitrarily large previous payloads. The common
        // trace stream stays allocation-free after reaching its high water.
        if (bytes.capacity()>1024*1024) {
            std::string().swap(bytes);
            frame=Json::object();
        }
    }
};
#endif
