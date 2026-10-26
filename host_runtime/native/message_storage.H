// SPDX-License-Identifier: GPL-3.0-or-later
// Private message implementation only. No class layout, wire or ownership change.
#include <array>
#include <atomic>
#include <mutex>

namespace {
constexpr size_t v08_storage_slots=32, v08_storage_fields=64;
constexpr size_t v08_storage_capacity=64*1024;
static std::atomic<bool> v08_storage_live{false};
struct V08PropertyStorage {
    std::mutex mutex;
    std::array<SPELLipcMessage::Properties,v08_storage_slots> maps;
    std::array<std::string,v08_storage_slots> ids,senders,receivers;
    size_t used=0, nextVictim=0;
    V08PropertyStorage() { v08_storage_live.store(true); }
    ~V08PropertyStorage() { v08_storage_live.store(false); }
};
static V08PropertyStorage v08_property_storage;

static bool v08_same_keys(const SPELLipcMessage::Properties& a,
                          const SPELLipcMessage::Properties& b)
{
    if (a.size()!=b.size()) return false;
    auto j=b.begin();
    for (const auto& field:a) {
        if (field.first!=j->first) return false;
        ++j;
    }
    return true;
}

void v08_acquire_message(SPELLipcMessage::Properties& target,std::string& id,
                         std::string& sender,std::string& receiver,
                         const SPELLipcMessage::Properties& source)
{
    if (&target==&source || !target.empty() || source.empty()
        || source.size()>v08_storage_fields || !v08_storage_live.load()) return;
    auto& cache=v08_property_storage;
    std::unique_lock<std::mutex> lock(cache.mutex,std::try_to_lock);
    if (!lock.owns_lock() || !cache.used) return;
    size_t index=cache.used;
    // Preserve distinct shapes while there is room; only a full cache may
    // evict a different shape. A repeated LINE/ACK/control stream stabilizes.
    for (size_t i=cache.used;i>0;--i)
        if (v08_same_keys(cache.maps[i-1],source)) { index=i-1; break; }
    if (index==cache.used) {
        if (cache.used<v08_storage_slots) return;
        index=cache.nextVictim;
        cache.nextVictim=(index+1)%v08_storage_slots;
    }
    target.swap(cache.maps[index]); id.swap(cache.ids[index]);
    sender.swap(cache.senders[index]); receiver.swap(cache.receivers[index]);
    const auto last=--cache.used;
    if (index!=last) {
        cache.maps[index].swap(cache.maps[last]);
        cache.ids[index].swap(cache.ids[last]);
        cache.senders[index].swap(cache.senders[last]);
        cache.receivers[index].swap(cache.receivers[last]);
    }
    // Empty-target assignment may have held oversized metadata. The vacated
    // slot owns that old storage; release it instead of retaining it unbounded.
    std::string().swap(cache.ids[last]);
    std::string().swap(cache.senders[last]);
    std::string().swap(cache.receivers[last]);
}

void v08_copy_properties(SPELLipcMessage::Properties& target,
                         const SPELLipcMessage::Properties& source)
{
    if (&target==&source) return;
    auto current=target.begin();
    for (const auto& field:source) {
        while (current!=target.end() && current->first<field.first)
            current=target.erase(current);
        if (current==target.end() || field.first<current->first)
            target.emplace_hint(current,field.first,field.second);
        else {
            current->second.assign(field.second);
            ++current;
        }
    }
    target.erase(current,target.end());
}

void v08_recycle_properties(SPELLipcMessage::Properties& properties,std::string& id,
                            std::string& sender,std::string& receiver) noexcept
{
    if (properties.empty() || properties.size()>v08_storage_fields
        || !v08_storage_live.load()) return;
    size_t capacity=0;
    for (const auto* value:{&id,&sender,&receiver}) {
        if (value->capacity()>v08_storage_capacity-capacity) return;
        capacity+=value->capacity();
    }
    for (const auto& field:properties) {
        if (field.first.capacity()>v08_storage_capacity-capacity) return;
        capacity+=field.first.capacity();
        if (field.second.capacity()>v08_storage_capacity-capacity) return;
        capacity+=field.second.capacity();
    }
    try {
        auto& cache=v08_property_storage;
        std::unique_lock<std::mutex> lock(cache.mutex,std::try_to_lock);
        if (!lock.owns_lock() || cache.used==v08_storage_slots) return;
        for (auto& field:properties) field.second.clear();
        id.clear(); sender.clear(); receiver.clear();
        properties.swap(cache.maps[cache.used]); id.swap(cache.ids[cache.used]);
        sender.swap(cache.senders[cache.used]); receiver.swap(cache.receivers[cache.used]);
        ++cache.used;
    } catch (...) {
        // Destruction remains noexcept; uncached values use ordinary destruction.
    }
}
}
