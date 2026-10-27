// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_MESSAGE_WORKERS_H
#define OPENBEXI_V08_MESSAGE_WORKERS_H
#include <array>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <thread>

// A ticket belongs to one message until its owner has joined it. No payload,
// listener or ticket is retained by an idle worker. Access is under pool.mutex.
struct V08MessageTicket {
    bool pooled = false;
    bool done = false;
};

// Reuse idle OS threads, without queueing or limiting callback concurrency.
// If the reusable slots are busy (or thread creation fails), the caller uses the
// original dedicated-thread path. MESSAGE and explicitly enabled REQUEST
// callbacks share the slots. Native measurement at 3a970c45 observed five
// simultaneous callbacks in Context, with thousands of dedicated fallbacks
// from one slot. Create slots lazily, so sequential work still uses one thread.
// A nested callback/request uses an idle slot or the original dedicated
// fallback, so a callback can synchronously wait without queueing work behind
// itself. Callback cancellation never interrupts or reuses a live
// ticket; the owner must join before destroying/recycling its object.
class V08MessageWorkers {
public:
    static constexpr size_t capacity = 5;
    V08MessageWorkers() = default;
    V08MessageWorkers(const V08MessageWorkers&) = delete;
    V08MessageWorkers& operator=(const V08MessageWorkers&) = delete;
    ~V08MessageWorkers() { shutdown(); }

    bool tryStart(void* object, void (*invoke)(void*), V08MessageTicket& ticket) {
        std::unique_lock<std::mutex> lock(mutex);
        if (stopping || ticket.pooled) return false;
        for (auto& slot : slots) {
            if (slot.object || slot.retired) continue;
            if (!slot.thread.joinable()) {
                try { slot.thread = std::thread([this, &slot] { work(slot); }); }
                catch (...) { return false; }
            }
            ticket.pooled = true;
            ticket.done = false;
            slot.object = object;
            slot.invoke = invoke;
            slot.ticket = &ticket;
            changed.notify_all();
            return true;
        }
        return false;
    }

    void join(V08MessageTicket& ticket) {
        std::unique_lock<std::mutex> lock(mutex);
        changed.wait(lock, [&ticket] { return ticket.done; });
    }

    // Called once by the owning process at teardown, after ordinary IPC drain.
    // Already accepted callbacks finish before any worker is joined/destroyed.
    void shutdown() {
        {
            std::lock_guard<std::mutex> lock(mutex);
            stopping = true;
            changed.notify_all();
        }
        for (auto& slot : slots) if (slot.thread.joinable()) slot.thread.join();
    }

private:
    struct Slot {
        std::thread thread;
        void* object = nullptr;
        void (*invoke)(void*) = nullptr;
        V08MessageTicket* ticket = nullptr;
        bool retired = false;
    };
    std::mutex mutex;
    std::condition_variable changed;
    std::array<Slot, capacity> slots;
    bool stopping = false;

    void work(Slot& slot) {
        // Declare before the lock so forced unwinding first releases any owned
        // lock, then settles the ticket after all callback frames have unwound.
        // An exited OS thread cannot be selected as a reusable idle worker.
        // Its bounded handle remains owned here and is joined at shutdown;
        // further callbacks retain the original dedicated-thread fallback.
        auto retire = [this, &slot](Slot*) {
            std::lock_guard<std::mutex> lock(mutex);
            slot.retired = true;
            if (slot.ticket) slot.ticket->done = true;
            slot.ticket = nullptr;
            slot.object = nullptr;
            slot.invoke = nullptr;
            changed.notify_all();
        };
        std::unique_ptr<Slot, decltype(retire)> lifetime(&slot, retire);
        std::unique_lock<std::mutex> lock(mutex);
        for (;;) {
            changed.wait(lock, [&] { return stopping || slot.object; });
            if (!slot.object) return;
            auto object = slot.object;
            auto invoke = slot.invoke;
            lock.unlock();
            // Preserve the native callback's exception policy. Its completion
            // guard runs on unwinding; an uncaught exception remains fatal.
            invoke(object);
            lock.lock();
            slot.ticket->done = true;
            slot.ticket = nullptr;
            slot.object = nullptr;
            slot.invoke = nullptr;
            changed.notify_all();
        }
    }
};
#endif
