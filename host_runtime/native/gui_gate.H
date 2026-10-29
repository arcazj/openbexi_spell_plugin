// SPDX-License-Identifier: GPL-3.0-or-later
#include "admission_ipc.H"

// One continuously owned serializer per callback thread. This is request
// staging storage, not an allocator pool: no independently owned message,
// acknowledgement, authority result or socket survives a call. Reentrant calls
// use their own workspace and cannot overwrite an in-flight request.
class V08GuiAdmissionWorkspace {
    using Json = nlohmann::json;
    Json body = Json::object();
    Json::object_t retiredFields;
    Json::object_t::node_type epochNode;
    std::string bytes;
    nlohmann::detail::serializer<Json> serializer;

    static void text(Json& target, const std::string& value) {
        if (target.is_string()) target.get_ref<Json::string_t&>().assign(value);
        else target = value;
    }

    void reset() noexcept {
        auto& active = body.at("fields").get_ref<Json::object_t&>();
        for (auto it = active.begin(); it != active.end();) {
            const auto field = it++;
            if (retiredFields.size() < fieldLimit && field->first.capacity() <= keyLimit
                && field->second.is_string()
                && field->second.get_ref<const Json::string_t&>().capacity() <= valueLimit) {
                field->second.get_ref<Json::string_t&>().clear();
                retiredFields.insert(active.extract(field));
            } else active.erase(field);
        }
        body.at("key") = 0; body.at("request") = false;
        auto& operation = body.at("operation").get_ref<Json::string_t&>();
        if (operation.capacity() > keyLimit) std::string().swap(operation);
        else operation.clear();
        auto& object = body.get_ref<Json::object_t&>();
        epochNode = object.extract("runtime_epoch");
        if (!epochNode.empty() && epochNode.mapped().is_string())
            epochNode.mapped().get_ref<Json::string_t&>().clear();
        if (bytes.capacity() > wireLimit) std::string().swap(bytes);
        else bytes.clear();
        busy = false;
    }

public:
    static constexpr std::size_t fieldLimit = 64, keyLimit = 128,
                                 valueLimit = 4096, wireLimit = 65536;
    bool busy = false;
    V08GuiAdmissionWorkspace()
        : serializer(nlohmann::detail::output_adapter<char>(bytes), ' ', Json::error_handler_t::strict) {
        body["fields"] = Json::object(); body["key"] = 0;
        body["operation"] = ""; body["request"] = false;
        body["schema"] = "openbexi.native-gui/1";
    }
    V08GuiAdmissionWorkspace(const V08GuiAdmissionWorkspace&) = delete;
    V08GuiAdmissionWorkspace& operator=(const V08GuiAdmissionWorkspace&) = delete;

    void admit(const SPELLipcMessage& message, bool request) {
        if (busy) throw std::logic_error("Native GUI workspace already owned");
        busy = true;
        struct Release { V08GuiAdmissionWorkspace& owner; ~Release() { owner.reset(); } } release{*this};
        auto& active = body.at("fields").get_ref<Json::object_t&>();
        for (const auto& field : message.v08Fields()) {
            // Descriptive socket user label, never an authority credential.
            if (field.first == "User") continue;
            auto saved = retiredFields.extract(field.first);
            if (!saved.empty()) active.insert(std::move(saved));
            text(body.at("fields")[field.first], field.second);
        }
        body.at("key") = message.getKey(); body.at("request") = request;
        text(body.at("operation"), message.getId());
        // Absence of the environment variable must omit the field, including
        // after a previous call supplied an epoch. Every present epoch is read
        // afresh before the provider is checked and the packet is serialized.
        v08_native_request_in_place(body, [this](const Json& value) -> const std::string& {
            bytes.clear(); serializer.dump(value, false, false, 0); bytes += '\n';
            return bytes;
        }, &epochNode);
    }

    std::size_t retainedFields() const noexcept { return retiredFields.size(); }
    std::size_t retainedStringCapacity() const {
        std::size_t capacity = bytes.capacity();
        for (const auto& field : retiredFields)
            capacity += field.first.capacity() + field.second.get_ref<const Json::string_t&>().capacity();
        for (const auto& field : body.get_ref<const Json::object_t&>()) {
            capacity += field.first.capacity();
            if (field.second.is_string()) capacity += field.second.get_ref<const Json::string_t&>().capacity();
        }
        if (!epochNode.empty()) {
            capacity += epochNode.key().capacity();
            if (epochNode.mapped().is_string()) capacity += epochNode.mapped().get_ref<const Json::string_t&>().capacity();
        }
        return capacity;
    }
    bool empty() const {
        if (busy || !bytes.empty() || !body.at("fields").empty()
            || !body.at("operation").get_ref<const Json::string_t&>().empty()
            || body.contains("runtime_epoch")) return false;
        for (const auto& field : retiredFields)
            if (!field.second.get_ref<const Json::string_t&>().empty()) return false;
        return epochNode.empty() || !epochNode.mapped().is_string()
            || epochNode.mapped().get_ref<const Json::string_t&>().empty();
    }
};

static V08GuiAdmissionWorkspace& v08_gui_workspace() {
    static thread_local V08GuiAdmissionWorkspace workspace;
    return workspace;
}
static void v08_admit_gui(const SPELLipcMessage& message, bool request)
{
    auto& workspace = v08_gui_workspace();
    if (workspace.busy) {
        V08GuiAdmissionWorkspace nested;
        nested.admit(message, request);
    } else workspace.admit(message, request);
}
