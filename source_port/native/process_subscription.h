// SPDX-License-Identifier: GPL-3.0-or-later
// Snapshot ownership and in-flight callback fencing for the original manager.
class SPELLprocessSubscription {
    std::mutex mutex;
    std::condition_variable drained;
    bool enabled=true;
    size_t active=0;
    std::map<std::thread::id,size_t> callers;
    void finish() {
        std::lock_guard<std::mutex> lock(mutex);
        auto caller=callers.find(std::this_thread::get_id());
        if (--caller->second==0) callers.erase(caller);
        --active;drained.notify_all();
    }
public:
    SPELLprocessListener* const listener;
    explicit SPELLprocessSubscription(SPELLprocessListener* value):listener(value) {}
    template<class Function> void invoke(Function callback) {
        {
            std::lock_guard<std::mutex> lock(mutex);
            if (!enabled) return;
            ++active;++callers[std::this_thread::get_id()];
        }
        try { callback(listener); }
        catch (...) { finish();throw; }
        finish();
    }
    void cancel() {
        std::unique_lock<std::mutex> lock(mutex);
        enabled=false;
        auto caller=callers.find(std::this_thread::get_id());
        const size_t own=caller==callers.end() ? 0 : caller->second;
        // A listener may unregister from its own callback. Other callbacks
        // must finish before external owner teardown proceeds.
        drained.wait(lock,[&]{return active<=own;});
    }
};
