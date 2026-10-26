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
    size_t used=0;
    V08PropertyStorage() { v08_storage_live.store(true); }
    ~V08PropertyStorage() { v08_storage_live.store(false); }
};
static V08PropertyStorage v08_property_storage;

static void v08_take_properties(SPELLipcMessage::Properties& target)
{
    if (!target.empty() || !v08_storage_live.load()) return;
    std::unique_lock<std::mutex> lock(v08_property_storage.mutex,std::try_to_lock);
    if (lock.owns_lock() && v08_property_storage.used)
        target.swap(v08_property_storage.maps[--v08_property_storage.used]);
}

void v08_copy_properties(SPELLipcMessage::Properties& target,
                         const SPELLipcMessage::Properties& source)
{
    if (&target==&source) return;
    v08_take_properties(target);
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
