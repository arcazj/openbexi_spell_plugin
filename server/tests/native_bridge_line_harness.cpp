// SPDX-License-Identifier: GPL-3.0-or-later
// Actual source-extracted bridge line loops; no native transport is simulated.
#include <nlohmann/json.hpp>
#include <iostream>
#include <sstream>
#include <string>
#include <stdexcept>
#include <vector>
#include <cstdint>
using Json=nlohmann::json;
static bool measuring=false;
static size_t allocations=0,allocated=0;
extern "C" void __sanitizer_malloc_hook(const volatile void*,size_t size) {
    if(measuring){++allocations;allocated+=size;}
}
static void require(bool ok){if(!ok)throw std::runtime_error("line invariant failed");}
static uint64_t digest=1469598103934665603ULL;
static void record(const std::string& value){for(unsigned char c:value){digest^=c;digest*=1099511628211ULL;}}
#include "bridge_line_loops.inc"
static std::string payload(size_t size){
    require(size>=2);return "\""+std::string(size-2,'x')+"\"";
}
static Json behavior(const std::string& data,bool after,int flags=0,int exceptions=0){
    std::istringstream input(data);
    input.setstate(static_cast<std::ios::iostate>(flags));
    Json retained=Json::array();
    std::string error;
    digest=1469598103934665603ULL;
    try {
        input.exceptions(static_cast<std::ios::iostate>(exceptions));
        auto consume=[&](const std::string& line){
            record(line);
            retained.push_back(Json::parse(line));
        };
        if(after)bridgeLineAfter(input,consume);else bridgeLineBefore(input,consume);
    }catch(const Json::exception& e){error=std::to_string(e.id)+":"+e.what();}
    catch(const std::exception& e){error=e.what();}
    const auto state=input.rdstate();
    const auto position=input.rdbuf()->pubseekoff(0,std::ios::cur,std::ios::in);
    // The parsed objects must keep their own text after replacing stream storage.
    input.exceptions(std::ios::goodbit);input.str("replaced-stream-storage");
    for(const auto& item:retained)record(item.dump());
    return {{"accepted",retained.size()},{"digest",digest},{"error",error},
            {"state",state},{"position",static_cast<long long>(position)}};
}
int main(int argc,char**argv){
    require(argc==2);
    const std::string mode=argv[1];
    if(mode.rfind("alloc_",0)==0){
        const bool after=mode.find("_after")!=std::string::npos;
        const bool parse=mode.find("_parse_")!=std::string::npos;
        const size_t width=mode.find("_long_")!=std::string::npos?2048:128;
        const auto line=payload(width)+"\n";
        std::string data;data.reserve(line.size()*10001);
        for(unsigned i=0;i<10001;++i)data+=line;
        std::istringstream input(data);
        size_t count=0;
        auto consume=[&](const std::string& value){
            if(parse){const auto parsed=Json::parse(value);record(parsed.get_ref<const std::string&>());}
            else record(value);
            if(count++==0){allocated=allocations=0;digest=1469598103934665603ULL;measuring=true;}
        };
        if(after)bridgeLineAfter(input,consume);else bridgeLineBefore(input,consume);
        measuring=false;
        require(count==10001);
        std::cout<<Json{{"iterations",10000},{"allocations",allocations},
            {"allocated_bytes",allocated},{"digest",digest}}.dump()<<std::endl;
        return 0;
    }
    std::string data;
    size_t accepted=0;
    int flags=0,exceptions=0;
    bool rejected=false;
    if(mode=="empty")data="";
    else if(mode=="empty_line")data="\n{\"unread\":true}\n";
    else if(mode=="unterminated"){data="{\"value\":97}";accepted=1;}
    else if(mode=="crlf"){data="{\"value\":97}\r\n";accepted=1;}
    else if(mode=="empty_after_valid"){data="{}\n\n{\"unread\":true}\n";accepted=1;}
    else if(mode=="embedded_nul"){data=std::string("\"a\0b\"\n",6);rejected=true;}
    else if(mode=="malformed"){data="{}\ninvalid\n{}\n";accepted=1;rejected=true;}
    else if(mode=="unicode"){data=u8"{\"value\":\"é中🙂\"}\n";accepted=1;}
    else if(mode=="binary_escape"){data="{\"value\":\"a\\u0000b\"}\n";accepted=1;}
    else if(mode=="mixed_sizes"){
        for(size_t n:{2,15,16,31,64,65536,2,4096,17,2})data+=payload(n)+"\n";
        accepted=10;
    }
    else if(mode=="limit_minus_one"){data=payload(4*1024*1024-1)+"\n";accepted=1;}
    else if(mode=="limit"){data=payload(4*1024*1024)+"\n";accepted=1;}
    else if(mode=="limit_eof"){data=payload(4*1024*1024);accepted=1;}
    else if(mode=="oversize"){data=payload(4*1024*1024+1)+"\n{}\n";rejected=true;}
    else if(mode=="oversize_after_small"){data="{}\n"+payload(4*1024*1024+1);accepted=1;rejected=true;}
    else if(mode=="failbit"){data="{}\n";flags=std::ios::failbit;}
    else if(mode=="badbit"){data="{}\n";flags=std::ios::badbit;}
    else if(mode=="eofbit"){data="{}\n";flags=std::ios::eofbit;}
    else if(mode=="eof_exception"){data="{}";exceptions=std::ios::eofbit;rejected=true;}
    else if(mode=="fail_exception"){data="{}\n";exceptions=std::ios::failbit;accepted=1;rejected=true;}
    else if(mode=="invalid_utf8"){data=std::string("\"\xff\"\n",4);rejected=true;}
    else throw std::runtime_error("unknown case");
    const auto before=behavior(data,false,flags,exceptions),after=behavior(data,true,flags,exceptions);
    require(before==after);
    require(after.at("accepted")==accepted);
    require(after.at("error").get<std::string>().empty()!=rejected);
    if(mode.rfind("oversize",0)==0)require(after.at("error")=="Host message exceeds 4 MiB");
    // Compare the original exception bytes above; make only the JSON report UTF-8 safe.
    std::cout<<after.dump(-1,' ',false,Json::error_handler_t::replace)<<std::endl;
}
