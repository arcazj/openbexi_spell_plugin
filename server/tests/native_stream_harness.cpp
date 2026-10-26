// SPDX-License-Identifier: GPL-3.0-or-later
// Real frozen/candidate message and output methods; unrelated dependencies are fixtures.
#include "SPELL_IPC/SPELLipcMessage.H"
#include <iostream>
#include <stdexcept>
#include <utility>
static bool measuring=false;
static size_t allocated=0, allocations=0;
extern "C" void __sanitizer_malloc_hook(const volatile void*, size_t size) {
    if (measuring) {allocated+=size; ++allocations;}
}
static void require(bool ok) {if (!ok) throw std::runtime_error("stream invariant failed");}
static uint64_t digest=1469598103934665603ULL;
static void record(const std::string& data) {
    for (unsigned char c:data) {digest^=c; digest*=1099511628211ULL;}
}
#include "native_output_harness.inc"
static void decode(SPELLipcMessage& message,const std::string& packet) {
#if V08_STREAM_CANDIDATE
    message.v08ReadData(packet);
#else
    message=SPELLipcMessage(); message.fromData(packet);
#endif
}
int main(int argc,char** argv) {
    if (argc!=2) return 2;
    const std::string mode=argv[1];
    SPELLipcMessage source("notification-identifier-longer-than-sso");
    source.setSender("handoff-root-original-executor#0");
    source.setReceiver("original-controller-connection");
    source.setType(MSG_TYPE_NOTIFY_ASYNC);
    source.set("Csp","handoff/root/sequence/1234");
    source.set("ProcId","original-native-procedure#0");
    source.set("StageTitle",u8"héllo-中🙂-with-a-long-stage-title");
    source.set("Binary",std::string("abc\0\xffxyz",8));
    if (mode=="wire") {
        SPELLipcMessage parsed;
        for (int i=0;i<256;++i) {
            source.setSequence(i*9999);source.setKey(i);
            source.set("Binary",std::string(i,static_cast<char>(i)));
            source.setType(static_cast<SPELLipcMessageType>(i%12));
            auto packet=source.data();decode(parsed,packet);
            require(parsed.data()==packet);record(parsed.data());
            auto owned=parsed;decode(parsed,"");
            require(owned.data()==packet&&parsed.data()==SPELLipcMessage().data());
        }
        check_output(source);
    } else if (mode=="decode-allocations") {
        auto packet=source.data();SPELLipcMessage parsed;
        for (int i=0;i<10;++i) decode(parsed,packet);
        measuring=true;
        for (int i=0;i<10000;++i) decode(parsed,packet);
        measuring=false;
        require(parsed.data()==packet);
    } else if (mode=="output-allocations") {
        SPELLipcOutput out;out.m_socket.wire.reserve(4096);
        for (int i=0;i<10;++i) {out.m_socket.wire.clear();out.m_socket.calls=0;out.send(source);}
        measuring=true;
        for (int i=0;i<10000;++i) {out.m_socket.wire.clear();out.m_socket.calls=0;out.send(source);}
        measuring=false;
    } else if (mode=="large-and-failure") {
        for (bool compressed:{false,true}) {
            SPELLipcOutput out;
            source.setCompressed(compressed);
            source.set("large",std::string(2*1024*1024,'z'));
            out.send(source);
#if V08_STREAM_CANDIDATE
            require(out.m_v08Wire.empty()&&out.m_v08Wire.capacity()<=1024*1024);
#endif
            source.setCompressed(false);
            out.m_socket.calls=0;out.m_socket.failAt=2;bool failed=false;
            try {out.send(source);}catch(const SPELLipcError&) {failed=true;}
            require(failed);
#if V08_STREAM_CANDIDATE
            require(out.m_v08Wire.empty()&&out.m_v08Wire.capacity()<=1024*1024);
#endif
            source.set("large","now-small");
            out.m_socket.wire.clear();out.m_socket.calls=0;out.m_socket.failAt=0;
            out.send(source);
            SPELLipcOutput clean;clean.send(source);
            require(clean.m_socket.wire==out.m_socket.wire);record(out.m_socket.wire);
        }
    } else if (mode=="malformed") {
        auto packet=source.data();SPELLipcMessage target;
        for (size_t cut=1;cut<packet.size();++cut) {
            decode(target,packet);
            auto broken=packet.substr(0,cut);
            try {decode(target,broken);}catch(const SPELLipcError&) {
                require(target.getId()=="<void>");
            }
            decode(target,packet);require(target.data()==packet);
        }
#if V08_STREAM_CANDIDATE
        // A borrowed view must not require NUL termination or own packet storage.
        auto framed=std::string("!")+packet+"garbage";
        target.v08ReadData(std::string_view(framed).substr(1,packet.size()));
        require(target.data()==packet);
        framed.assign(framed.size(),'x');require(target.data()==packet);
#endif
    } else return 3;
    std::cout<<"{\"digest\":"<<digest<<",\"allocated_bytes\":"<<allocated
             <<",\"allocations\":"<<allocations<<"}"<<std::endl;
}
