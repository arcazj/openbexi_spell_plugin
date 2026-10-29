// SPDX-License-Identifier: GPL-3.0-or-later
// Uses the actual native message class, immutable former input loop and candidate loop.
#include "bridge_input.inc"

static Json check_bridge_input_ownership() {
    // A non-object outer request cannot reach the field loop: the bridge first
    // evaluates request.at("seq"). Field shapes and errors below match that boundary.
    const std::vector<Json> cases={
        Json::object(), Json{{"fields",Json::object()}}, Json{{"fields",nullptr}},
        Json{{"fields",Json::array()}}, Json{{"fields",Json::array({"x","y"})}},
        Json{{"fields","standalone string"}}, Json{{"fields",true}},
        Json{{"fields",123}}, Json{{"fields",Json{{"a","first"},{"z",42}}}},
        Json{{"fields",Json{{"empty",""},{"unicode",u8"é中🙂"}}}},
        Json{{"fields",Json{{"long",std::string(131072,'x')}}}},
        Json{{"fields",Json{{"binary",std::string("a\0b",3)}}}}
    };
    for(const auto& request:cases) {
        const auto original=request;
        SPELLipcMessage before("MSG_INPUT"),after("MSG_INPUT");
        std::string beforeError,afterError;
        try {bridgeInputBefore(before,request);} catch(const Json::exception& error) {
            beforeError=std::to_string(error.id)+":"+error.what();
        }
        try {bridgeInputAfter(after,request);} catch(const Json::exception& error) {
            afterError=std::to_string(error.id)+":"+error.what();
        }
        require(beforeError==afterError);
        require(before.data()==after.data());
        require(request==original);
        record(after.data());record(afterError);
    }
    SPELLipcMessage retained("MSG_INPUT");
    {
        Json request={{"fields",Json{{"owner",std::string(97,'a')}}}};
        bridgeInputAfter(retained,request);
        request["fields"]["owner"]=std::string(97,'b');
        require(retained.get("owner")==std::string(97,'a'));
        retained.set("owner","changed-native-owner");
        require(request["fields"]["owner"]==std::string(97,'b'));
        retained.clear();
        bridgeInputAfter(retained,request);
    }
    require(retained.get("owner")==std::string(97,'b'));
    record(retained.data());
    return {{"cases",cases.size()},{"input_unchanged",true},
            {"owned_after_request_destruction",true},{"digest",digest}};
}

static void measure_bridge_input(const std::string& mode) {
    Json request;
    if(mode.find("_short_")!=std::string::npos)
        request={{"fields",Json{{"ProcId","root"},{"Sequence","17"},{"Csp","2"}}}};
    else if(mode.find("_long_")!=std::string::npos)
        request={{"fields",Json{{"ProcId",std::string(97,'p')},{"Label",std::string(257,'q')}}}};
    else {
        require(mode.find("_absent_")!=std::string::npos);
        request=Json::object();
    }
    const bool copy=mode.find("_copy")!=std::string::npos;
    auto decode=[&]() {
        SPELLipcMessage message("MSG_INPUT");
        if(copy) bridgeInputBefore(message,request); else bridgeInputAfter(message,request);
        for(const auto& field:message.v08Fields()) {record(field.first);record(field.second);}
    };
    decode();
    digest=1469598103934665603ULL;
    allocated=allocations=0;
    measuring=true;
    for(unsigned index=0;index<10000;++index) decode();
    measuring=false;
}
