// SPDX-License-Identifier: GPL-3.0-or-later
// Included once by the rebuilt incoming implementation.
#include <array>
#include <atomic>
#include <mutex>
namespace {
std::atomic<bool> v08_message_instances_live{false};
struct V08MessageInstances {
    static constexpr size_t capacity=32;
    std::mutex mutex;
    std::array<SPELLipcIncomingMessage*,capacity> idle{};
    size_t used=0;
    V08MessageInstances(){v08_message_instances_live.store(true);}
    ~V08MessageInstances(){
        v08_message_instances_live.store(false);
        for(size_t i=0;i<used;++i)delete idle[i];
    }
};
V08MessageInstances v08_message_instances;
}

void SPELLipcIncomingBase::v08Reset(const std::string& id, const std::string& ifcName,
                                   const SPELLipcMessage& message,
                                   SPELLipcInterfaceListener& listener)
{
    // Only an exclusively owned, fully joined processor can be reset. Moving a
    // new independent message copy preserves input/handler payload separation.
    m_message=SPELLipcMessage(message);
    v08ResetThreadId(id);m_ifcName=ifcName;m_processingId=id;
    m_listener=&listener;m_key=message.getKey();
    m_started=false;m_finished=false;
    m_processingFinishEvent.clear();m_processingStartEvent.clear();
}

bool SPELLipcIncomingBase::v08Release()
{
    // No listener reference or message content survives in the idle cache.
    // Oversized identity buffers are destroyed through ordinary ownership.
    const bool bounded=v08ReleaseThreadId() && m_ifcName.capacity()<=1024
                       && m_processingId.capacity()<=1024;
    m_message.clear();m_message=SPELLipcMessage();
    m_ifcName.clear();m_processingId.clear();
    m_listener=nullptr;m_key=0;
    return bounded;
}

SPELLipcIncomingMessage* SPELLipcIncomingMessage::v08Create(
    const std::string& id,const std::string& ifcName,const SPELLipcMessage& message,
    SPELLipcInterfaceListener& listener)
{
    std::unique_ptr<SPELLipcIncomingMessage> instance;
    if(v08_message_instances_live.load()) {
        std::unique_lock<std::mutex> lock(v08_message_instances.mutex,std::try_to_lock);
        if(lock.owns_lock() && v08_message_instances.used) {
            auto& slot=v08_message_instances.idle[--v08_message_instances.used];
            instance.reset(slot);slot=nullptr;
        }
    }
    if(!instance)return new SPELLipcIncomingMessage(id,ifcName,message,listener);
    // Exception during reset leaves one local owner, which destroys the object.
    instance->v08Reset(id,ifcName,message,listener);
    return instance.release();
}

void SPELLipcIncomingMessage::v08Dispose()
{
    // The collector's join precedes this call. Cancellation alone is not enough
    // to return a processor while its callback can still access it.
    try {
      if(v08Release() && v08_message_instances_live.load()) {
        std::unique_lock<std::mutex> lock(v08_message_instances.mutex,std::try_to_lock);
        if(lock.owns_lock() && v08_message_instances.used<V08MessageInstances::capacity) {
            v08_message_instances.idle[v08_message_instances.used++]=this;
            return;
        }
      }
    } catch(...) {
        // Reuse is optional: if clearing/locking fails, retain ordinary deletion.
    }
    delete this;
}
