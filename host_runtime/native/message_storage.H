// SPDX-License-Identifier: GPL-3.0-or-later
// Private message implementation only. No class layout, wire or ownership change.
#include <array>
#include <atomic>
#include <mutex>
#include <cstdint>
#include <cstdio>
#include <unistd.h>
#define OPENBEXI_V08_MESSAGE_STORAGE 1

namespace {
// Copy temporaries cross short-lived IPC threads. A bounded process-local cache
// reuses their *owned* map nodes; no two live messages ever share a field map.
// Contention, exhaustion and oversized messages fall back to ordinary storage.
constexpr size_t v08_storage_slots=32, v08_storage_fields=64;
constexpr size_t v08_storage_capacity=64*1024;
static std::atomic<bool> v08_storage_live{false};
struct V08PropertyStorage {
    std::mutex mutex;
    std::array<SPELLipcMessage::Properties,v08_storage_slots> maps;
    size_t used=0, nextVictim=0;
    V08PropertyStorage() { v08_storage_live.store(true); }
    ~V08PropertyStorage() { v08_storage_live.store(false); }
};
static V08PropertyStorage v08_property_storage;

// Enabled only from main by the existing opt-in allocation profiler, before
// worker threads start. Fixed counters retain no message keys or values.
enum V08StorageMetric { node_requests, node_reused, node_unavailable,
    node_lock_miss, node_empty, copy_calls, copy_whole_map, copy_map_lock_miss,
    copy_shape_miss, copy_allocations, recycle_calls, recycle_empty, recycle_wide,
    recycle_capacity, recycle_unavailable, recycle_lock_miss, recycle_full,
    recycled_maps, storage_metric_count };
static std::atomic<bool> v08_storage_profile_enabled{false};
static std::array<std::atomic<uint64_t>,storage_metric_count> v08_storage_metrics{};
static void v08_storage_count(V08StorageMetric metric) noexcept {
    if(v08_storage_profile_enabled.load(std::memory_order_relaxed))
        v08_storage_metrics[metric].fetch_add(1,std::memory_order_relaxed);
}
static void v08_storage_profile_begin() noexcept {
    v08_storage_profile_enabled.store(true,std::memory_order_relaxed);
}
static void v08_storage_profile_dump(uint64_t tick) noexcept {
    if(!v08_storage_profile_enabled.load(std::memory_order_relaxed))return;
    static const char* names[]={"node_requests","node_reused","node_unavailable",
        "node_lock_miss","node_empty","copy_calls","copy_whole_map","copy_map_lock_miss",
        "copy_shape_miss","copy_allocations","recycle_calls","recycle_empty","recycle_wide",
        "recycle_capacity","recycle_unavailable","recycle_lock_miss","recycle_full",
        "recycled_maps"};
    static_assert(sizeof(names)/sizeof(*names)==storage_metric_count);
    char line[1536];
    int count=std::snprintf(line,sizeof(line),"V08_STORAGE pid=%ld tick=%llu",
        static_cast<long>(getpid()),static_cast<unsigned long long>(tick));
    for(size_t i=0;i<storage_metric_count;++i) {
        if(count<0 || static_cast<size_t>(count)>=sizeof(line))return;
        const int added=std::snprintf(line+count,sizeof(line)-count," %s=%llu",names[i],
            static_cast<unsigned long long>(v08_storage_metrics[i].load(std::memory_order_relaxed)));
        if(added<0 || static_cast<size_t>(added)>=sizeof(line)-count)return;
        count+=added;
    }
    if(count>0 && static_cast<size_t>(count)<sizeof(line)-1) {
        line[count++]='\n';const auto ignored=write(STDERR_FILENO,line,count);(void)ignored;
    }
}

// Producers can split a cached map while assembling a fresh message. Both
// producers and copies may take its remaining, exclusively owned nodes.
// Never hold the cache lock while changing strings or publishing into a message.
static SPELLipcMessage::Properties::node_type v08_take_property(const std::string& key)
{
    v08_storage_count(node_requests);
    SPELLipcMessage::Properties::node_type node;
    if (v08_storage_live.load()) {
        std::unique_lock<std::mutex> lock(v08_property_storage.mutex,std::try_to_lock);
        if (lock.owns_lock()) {
            auto& storage=v08_property_storage;
            size_t selected=storage.used;
            for (size_t index=storage.used;index>0;--index) {
                auto& candidate=storage.maps[index-1];
                auto field=candidate.find(key);
                if (field==candidate.end()) continue;
                node=candidate.extract(field);
                selected=index-1;
                break;
            }
            if (node.empty() && storage.used) {
                selected=storage.used-1;
                auto& candidate=storage.maps[selected];
                node=candidate.extract(candidate.begin());
            }
            if (!node.empty() && storage.maps[selected].empty()) {
                --storage.used;
                if (selected!=storage.used)
                    storage.maps[selected].swap(storage.maps[storage.used]);
            }
            v08_storage_count(node.empty()?node_empty:node_reused);
        } else v08_storage_count(node_lock_miss);
    } else v08_storage_count(node_unavailable);
    return node;
}

void v08_set_property(SPELLipcMessage::Properties& target,
                      std::string key, std::string value)
{
    auto found=target.find(key);
    if (found!=target.end()) {
        found->second.assign(value);
        return;
    }
    auto node=v08_take_property(key);
    if (node.empty()) {
        target.emplace(std::move(key),std::move(value));
    } else {
        node.key().assign(key);
        node.mapped().assign(value);
        target.insert(std::move(node));
    }
}

static bool v08_same_keys(const SPELLipcMessage::Properties& a,
                          const SPELLipcMessage::Properties& b)
{
    if (a.size()!=b.size()) return false;
    auto left=a.begin();
    for (const auto& field:b) {
        if (left->first!=field.first) return false;
        ++left;
    }
    return true;
}

static void v08_take_properties(SPELLipcMessage::Properties& target,
                               const SPELLipcMessage::Properties& source)
{
    if (!target.empty() || source.empty() || source.size()>v08_storage_fields
        || !v08_storage_live.load()) return;
    std::unique_lock<std::mutex> lock(v08_property_storage.mutex,std::try_to_lock);
    if (!lock.owns_lock()) {v08_storage_count(copy_map_lock_miss);return;}
    auto& storage=v08_property_storage;
    // LINE, ACK and control messages interleave. Taking the last map blindly
    // destroys one shape's nodes to construct the next. Keep distinct shapes
    // while there is room, and take only an exact key inventory after warm-up.
    for (size_t index=storage.used;index>0;--index) {
        auto& candidate=storage.maps[index-1];
        if (!v08_same_keys(candidate,source)) continue;
        target.swap(candidate);
        if (index!=storage.used) candidate.swap(storage.maps[storage.used-1]);
        --storage.used;
        v08_storage_count(copy_whole_map);
        return;
    }
    v08_storage_count(copy_shape_miss);
    // A cache filled by startup layouts must adapt to the running stream.
    // Replacing only the final slot makes all new layouts fight for that slot,
    // leaving the other 31 unused forever. Rotate the victim at fixed capacity.
    // Copy synchronization still removes absent keys before publication.
    if (storage.used==v08_storage_slots) {
        const size_t victim=storage.nextVictim;
        storage.nextVictim=(victim+1)%v08_storage_slots;
        target.swap(storage.maps[victim]);
        --storage.used;
        if (victim!=storage.used) storage.maps[victim].swap(storage.maps[storage.used]);
    }
}

void v08_copy_properties(SPELLipcMessage::Properties& target,
                         const SPELLipcMessage::Properties& source)
{
    v08_storage_count(copy_calls);
    if (&target==&source) return;
    v08_take_properties(target,source);
    auto current=target.begin();
    for (const auto& field:source) {
        while (current!=target.end() && current->first<field.first)
            current=target.erase(current);
        if (current==target.end() || field.first<current->first) {
            auto node=v08_take_property(field.first);
            if (node.empty()) {
                v08_storage_count(copy_allocations);
                target.emplace_hint(current,field.first,field.second);
            }
            else {
                node.key().assign(field.first);
                node.mapped().assign(field.second);
                target.insert(std::move(node));
            }
        } else {
            current->second.assign(field.second);
            ++current;
        }
    }
    target.erase(current,target.end());
}

void v08_recycle_properties(SPELLipcMessage::Properties& properties) noexcept
{
    v08_storage_count(recycle_calls);
    if (properties.empty()) {v08_storage_count(recycle_empty);return;}
    if (properties.size()>v08_storage_fields) {v08_storage_count(recycle_wide);return;}
    if (!v08_storage_live.load()) {v08_storage_count(recycle_unavailable);return;}
    size_t capacity=0;
    for (const auto& field:properties) {
        if (field.first.capacity()>v08_storage_capacity-capacity) {
            v08_storage_count(recycle_capacity);return;
        }
        capacity+=field.first.capacity();
        if (field.second.capacity()>v08_storage_capacity-capacity) {
            v08_storage_count(recycle_capacity);return;
        }
        capacity+=field.second.capacity();
    }
    try {
        std::unique_lock<std::mutex> lock(v08_property_storage.mutex,std::try_to_lock);
        if (!lock.owns_lock()) {v08_storage_count(recycle_lock_miss);return;}
        if (v08_property_storage.used==v08_storage_slots) {v08_storage_count(recycle_full);return;}
        // Retain capacity, not a readable previous value. Copy synchronization
        // removes absent keys before any newly constructed message is visible.
        for (auto& field:properties) field.second.clear();
        properties.swap(v08_property_storage.maps[v08_property_storage.used++]);
        v08_storage_count(recycled_maps);
    } catch (...) {
        // Destruction remains noexcept; uncached maps use their normal destructor.
    }
}
}
