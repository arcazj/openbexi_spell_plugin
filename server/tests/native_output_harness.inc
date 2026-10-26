// Test transport for the real frozen/patched send() and writeData() methods.
// Socket writes are captured (including partial writes/failures); compression
// uses zlib. This is component verification, separate from hosted native IPC.
#include <cerrno>
#include <iomanip>
#include <zlib.h>
#define NAME std::string("output-test")
#define SIZE sizeof(uint32_t)
#define MINIMUM_SIZE_FOR_COMPRESSION 512
#define LOG_ERROR(x) ((void)0)
struct SPELLmonitor { explicit SPELLmonitor(int&) {} };
struct SPELLcompression {
    std::string data;
    explicit SPELLcompression(const std::string& input):data(input) {}
    std::string compress() {
        uLongf size=compressBound(data.size());std::string out(size,'\0');
        if(compress2(reinterpret_cast<Bytef*>(out.data()),&size,
                     reinterpret_cast<const Bytef*>(data.data()),data.size(),Z_DEFAULT_COMPRESSION)!=Z_OK)
            throw std::runtime_error("compression failed");
        out.resize(size);return out;
    }
};
struct OutputSocket {
    std::string wire;int calls=0,failAt=0;
    int send(const char* bytes,int size) {
        if (++calls==failAt) {errno=EPIPE;return -1;}
        int count=calls==1?size:std::min(size,17);
        wire.append(bytes,count);return count;
    }
};
struct OutputChannel { int failures=0;void outputFailed(int,const std::string&) {++failures;} };
struct OutputTime { int updates=0;void setCurrent(){++updates;} };
struct SPELLipcOutput {
    int m_lock=0,m_key=97;bool m_connected=true;
    OutputSocket m_socket;OutputChannel m_channel;OutputTime m_lastSentTime;
    void send(SPELLipcMessage&);
    void writeData(std::string);
    void v08WriteData(const std::string&);
    std::string m_v08Wire;
};
#include "output_methods.inc"
#undef LOG_ERROR
#undef NAME

static void check_output(SPELLipcMessage& m) {
    for (bool compressed:{false,true}) {
        for (int size:{0,8,1024}) {
            m.setCompressed(compressed);m.set("Binary",std::string(size,'\0'));
            SPELLipcOutput out;out.send(m);
            const auto raw=m.data();
            const bool expected=compressed&&raw.size()>=MINIMUM_SIZE_FOR_COMPRESSION;
            std::string payload=(expected?COMPRESSION_FLAG_TRUE_STR:COMPRESSION_FLAG_FALSE_STR)
                +(expected?SPELLcompression(raw).compress():raw);
            const auto& wire=out.m_socket.wire;
            uint32_t length=0;for(int i=0;i<4;++i)length=(length<<8)|static_cast<unsigned char>(wire[i]);
            require(length==payload.size()&&wire.substr(4)==payload);
            require(out.m_channel.failures==0&&out.m_lastSentTime.updates==1);
            record(wire);
        }
    }
    for(int failure:{1,2,3}) {
        SPELLipcOutput out;out.m_socket.failAt=failure;bool rejected=false;
        try {out.send(m);}catch(const SPELLipcError&){rejected=true;}
        require(rejected&&out.m_channel.failures==1&&out.m_lastSentTime.updates==0);
    }
    SPELLipcOutput disconnected;disconnected.m_connected=false;disconnected.send(m);
    require(disconnected.m_socket.wire.empty()&&disconnected.m_lastSentTime.updates==0);
}
