// SPDX-License-Identifier: GPL-3.0-or-later
// Compare the exact dev82 input-transfer body with the extracted current body.
#include <thread>
#include "bridge_transfer.inc"

static Json transfer_result(const Json& request,bool before) {
    try {
        auto message=before?bridgeTransferBefore(request):bridgeTransferAfter(request);
        return {{"wire",message.data()},{"id",message.getId()},
                {"receiver",message.getReceiver()},{"fields",message.v08Fields()}};
    } catch(const Json::exception& error) {
        // Preserve both the library error identity and the public bridge frame.
        return {{"error_id",error.id},{"frame",Json{{"seq",7},{"ok",false},{"error",error.what()}}}};
    }
}

static Json transfer_request() {
    return {{"seq",7},{"operation","send"},{"id","MSG_INPUT"},{"receiver","CTX"}};
}

static void check_transfer(const Json& request) {
    const auto original=request;
    const auto before=transfer_result(request,true),after=transfer_result(request,false);
    require(before==after&&request==original);
    record(after.dump(-1,' ',false,Json::error_handler_t::replace));
}

static void check_bridge_transfer(const std::string& mode) {
    if(mode=="bridge_transfer_shapes") {
        const std::vector<Json> shapes={nullptr,true,false,0,-1,1.25,Json::array(),
            Json::array({"x","y"}),Json::object(),Json{{"a","first"},{"z",42}},
            "",u8"é中🙂",std::string("a\0b",3),Json::binary({0,1,255})};
        check_transfer(transfer_request());
        for(const auto& name:{"id","receiver","fields"}) {
            auto missing=transfer_request();missing.erase(name);check_transfer(missing);
            for(const auto& shape:shapes) {
                auto request=transfer_request();request[name]=shape;check_transfer(request);
            }
        }
        for(const auto& shape:shapes) {
            auto request=transfer_request();request["fields"]={{"a","first"},{"z",shape}};
            check_transfer(request);
        }
        auto request=transfer_request();
        request["fields"]={{"","empty-key"},{"Id","reserved"},{"ReceiverId","field-receiver"},
                           {std::string("k\0x",3),std::string("v\0y",3)}};
        check_transfer(request);
        check_transfer(Json::parse("{\"id\":\"first\",\"id\":\"last\",\"receiver\":\"CTX\",\"fields\":{\"k\":\"a\",\"k\":\"b\"}}"));
    } else if(mode=="bridge_transfer_ownership") {
        SPELLipcMessage retained;
        std::string expected;
        {
            auto request=transfer_request();request["id"]=std::string(97,'i');
            request["receiver"]=std::string(257,'r');
            request["fields"]={{std::string(97,'k'),std::string(257,'v')},{"binary",std::string("a\0b",3)}};
            retained=bridgeTransferAfter(request);expected=retained.data();
            request["id"]="changed-id";request["receiver"]="changed-receiver";
            request["fields"]=nullptr;
            require(retained.data()==expected);
            request.clear();require(retained.data()==expected);
        }
        require(retained.data()==expected);record(expected);
        auto independent=retained;
        retained.set("binary","changed-native");retained.setId("changed-native-id");
        require(independent.data()==expected);record(independent.data());
    } else if(mode=="bridge_transfer_sizes") {
        for(size_t size:{size_t(0),size_t(15),size_t(16),size_t(17),size_t(4095),
                         size_t(4096),size_t(4097),size_t(65535),size_t(2*1024*1024)}) {
            auto request=transfer_request();request["id"]=std::string(size,'i');
            request["receiver"]=std::string(size,'r');request["fields"]={{"long",std::string(size,'v')}};
            check_transfer(request);
        }
        // The bridge's unchanged line-reader separately enforces 4 MiB. Native
        // wire bounds and ownership are checked here without raising that limit.
        auto request=transfer_request();request["fields"]={{std::string(65535,'k'),"value"}};
        check_transfer(request);
        request["fields"]={{std::string(65536,'k'),"value"}};
        bool before=false,after=false;
        try {bridgeTransferBefore(request).data();} catch(const SPELLipcError&) {before=true;}
        try {bridgeTransferAfter(request).data();} catch(const SPELLipcError&) {after=true;}
        require(before&&after);
    } else if(mode=="bridge_transfer_updates") {
#if V08_CODEC_REUSE
        SPELLipcMessage before(std::string(97,'i'));
        auto after=SPELLipcMessage::v08FromId(std::string(97,'i'));
        for(size_t size:{size_t(0),size_t(257),size_t(3),size_t(4097),size_t(16)}) {
            std::string key(97,'k'),value(size,'v'),receiver(size,'r');
            before.set(key,value);after.v08Set(key,value);
            before.setReceiver(receiver);after.v08SetReceiver(receiver);
            value.assign(500,'x');key.assign(500,'y');receiver.assign(500,'z');
            require(before.data()==after.data());record(after.data());
            // Updating an existing value and self-assignment must remain owned.
            after.v08Set(std::string(97,'k'),after.getRef(std::string(97,'k')));
            after.v08SetReceiver(after.v08TestReceiver());
            require(before.data()==after.data());
            auto independent=after;after.set("other","unrelated");
            require(independent.data()==before.data());
            before.set("other","unrelated");
        }
#endif
    } else if(mode=="bridge_transfer_threads") {
        std::vector<std::thread> threads;
        std::vector<std::string> results(8);
        std::atomic<bool> valid{true};
        for(size_t index=0;index<results.size();++index) threads.emplace_back([&,index]() {
            try {
                for(unsigned turn=0;turn<200;++turn) {
                    auto request=transfer_request();request["id"]=std::string(97,char('a'+index));
                    request["receiver"]=std::string(257,char('A'+index));
                    request["fields"]={{"index",std::to_string(index)},{"turn",std::to_string(turn)},
                                       {std::string(97,'k'),std::string(257,char('a'+index))}};
                    const auto before=bridgeTransferBefore(request).data();
                    auto after=bridgeTransferAfter(request);request.clear();
                    if(after.data()!=before)valid=false;
                    if(turn==199)results[index]=after.data();
                }
            } catch(...) {valid=false;}
        });
        for(auto& thread:threads)thread.join();
        require(valid.load());for(const auto& result:results)record(result);
    } else require(false);
}

static void measure_bridge_transfer(const std::string& mode) {
    auto request=transfer_request();
    if(mode.find("long_values")!=std::string::npos)
        request["fields"]={{"ProcId",std::string(97,'p')},{"Label",std::string(257,'q')}};
    else if(mode.find("long_headers")!=std::string::npos) {
        request["id"]=std::string(97,'i');request["receiver"]=std::string(257,'r');
    } else if(mode.find("long_keys")!=std::string::npos)
        request["fields"]={{std::string(97,'k'),"one"},{std::string(257,'q'),"two"}};
    else {require(mode.find("short")!=std::string::npos);request["fields"]={{"ProcId","root"},{"Sequence","17"}};}
    const bool before=mode.find("_before")!=std::string::npos;
    auto transfer=[&]() {
        auto message=before?bridgeTransferBefore(request):bridgeTransferAfter(request);
        // Read-only harness accessors avoid measurement-only copied getters.
        record(message.v08TestId());record(message.v08TestReceiver());
        for(const auto& field:message.v08Fields()) {record(field.first);record(field.second);}
    };
    transfer();digest=1469598103934665603ULL;allocated=allocations=0;measuring=true;
    for(unsigned index=0;index<10000;++index)transfer();
    measuring=false;
}
