// SPDX-License-Identifier: GPL-3.0-or-later
// A received ACK can settle only its currently owned logical notification.
#ifndef OPENBEXI_V08_ACKNOWLEDGEMENT_OWNERSHIP_H
#define OPENBEXI_V08_ACKNOWLEDGEMENT_OWNERSHIP_H
#include <atomic>
#include <climits>
#include <cstddef>
#include <mutex>
#include <stdexcept>
#include <string>
#include <utility>

// Native ISTR takes signed long. Sequence is an opaque string throughout the
// actual bridge/Context/CIF ACK path; STRI parses only the separate IpcSeq header.
// Reserve LONG_MAX once, then keep a saturated sentinel instead of wrapping.
inline unsigned long v08ReserveNotificationSequence(std::atomic<unsigned long>& next)
{
    auto value=next.load(std::memory_order_relaxed);
    for (;;) {
        if(value>static_cast<unsigned long>(LONG_MAX))
            throw std::overflow_error("Native notification sequence exhausted");
        if(next.compare_exchange_weak(value,value+1,std::memory_order_relaxed,
                                      std::memory_order_relaxed)) return value;
    }
}

class V08AcknowledgementOwners {
public:
    class Ticket {
        friend class V08AcknowledgementOwners;
        V08AcknowledgementOwners& owner;
        const std::string sequence;
        Ticket* next=nullptr;
        unsigned long generation=0;
        bool armed=false,received=false;
    public:
        Ticket(V08AcknowledgementOwners& ledger,std::string value):owner(ledger),sequence(std::move(value))
        {
            std::lock_guard<std::mutex> lock(owner.mutex);
            for(auto* item=owner.first;item;item=item->next)
                if(item->sequence==sequence) throw std::logic_error("Native acknowledgement already owned");
            next=owner.first;owner.first=this;++owner.active;
        }
        Ticket(const Ticket&)=delete;
        Ticket& operator=(const Ticket&)=delete;
        ~Ticket()
        {
            std::lock_guard<std::mutex> lock(owner.mutex);
            Ticket** cursor=&owner.first;
            while(*cursor!=this) cursor=&(*cursor)->next;
            *cursor=next;--owner.active;
        }
        void arm(unsigned long currentGeneration)
        {
            std::lock_guard<std::mutex> lock(owner.mutex);
            // A retry still owns the same immutable logical notification.
            // Preserve its earlier receipt across a connection-generation
            // transition; no different notification can reuse this sequence.
            generation=currentGeneration;armed=true;
        }
    };
    V08AcknowledgementOwners()=default;
    V08AcknowledgementOwners(const V08AcknowledgementOwners&)=delete;
    V08AcknowledgementOwners& operator=(const V08AcknowledgementOwners&)=delete;
    bool receive(const std::string& sequence)
    {
        std::lock_guard<std::mutex> lock(mutex);
        for(auto* item=first;item;item=item->next) {
            if(item->sequence==sequence && item->armed) {
                const bool firstReceipt=!item->received;
                item->received=true;return firstReceipt;
            }
        }
        // Pings, stale ACKs and ACKs for cancelled calls retain no credit.
        return false;
    }
    bool consume(const std::string& sequence,unsigned long generation)
    {
        std::lock_guard<std::mutex> lock(mutex);
        for(auto* item=first;item;item=item->next) {
            if(item->sequence==sequence && item->generation==generation && item->armed && item->received) {
                item->armed=false;item->received=false;return true;
            }
        }
        return false;
    }
    std::size_t pending() const
    {
        std::lock_guard<std::mutex> lock(mutex);return active;
    }
private:
    mutable std::mutex mutex;
    Ticket* first=nullptr;
    std::size_t active=0;
};
#endif
