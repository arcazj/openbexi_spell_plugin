// SPDX-License-Identifier: GPL-3.0-or-later
// Private message implementation only. No class layout, wire or ownership change.
#include <array>
#include <atomic>
#include <mutex>

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

// Producers can split a cached map while assembling a fresh message. Both
// producers and copies may take its remaining, exclusively owned nodes.
// Never hold the cache lock while changing strings or publishing into a message.
static SPELLipcMessage::Properties::node_type v08_take_property(const std::string& key)
{
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
        }
    }
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
    if (!lock.owns_lock()) return;
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
        return;
    }
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
    if (&target==&source) return;
    v08_take_properties(target,source);
    auto current=target.begin();
    for (const auto& field:source) {
        while (current!=target.end() && current->first<field.first)
            current=target.erase(current);
        if (current==target.end() || field.first<current->first) {
            auto node=v08_take_property(field.first);
            if (node.empty()) target.emplace_hint(current,field.first,field.second);
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
    if (properties.empty() || properties.size()>v08_storage_fields
        || !v08_storage_live.load()) return;
    size_t capacity=0;
    for (const auto& field:properties) {
        if (field.first.capacity()>v08_storage_capacity-capacity) return;
        capacity+=field.first.capacity();
        if (field.second.capacity()>v08_storage_capacity-capacity) return;
        capacity+=field.second.capacity();
    }
    try {
        std::unique_lock<std::mutex> lock(v08_property_storage.mutex,std::try_to_lock);
        if (!lock.owns_lock() || v08_property_storage.used==v08_storage_slots) return;
        // Retain capacity, not a readable previous value. Copy synchronization
        // removes absent keys before any newly constructed message is visible.
        for (auto& field:properties) field.second.clear();
        properties.swap(v08_property_storage.maps[v08_property_storage.used++]);
    } catch (...) {
        // Destruction remains noexcept; uncached maps use their normal destructor.
    }
}
}
