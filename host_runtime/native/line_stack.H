// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_LINE_STACK_H
#define OPENBEXI_V08_LINE_STACK_H
#include <array>
#include <charconv>
#include <string>

// Scope-owned scratch for synchronous stack snapshots. Reentrant calls use
// distinct slots, and exhaustion uses ordinary local storage. No callback,
// message, frame or authority proof is retained in an idle slot.
class V08LineStack {
    struct Cache {
        std::array<std::string,8> values;
        std::array<bool,8> busy{};
    };
    static Cache& cache() { static thread_local Cache value; return value; }
    std::string fallback;
    size_t slot=8;
public:
    V08LineStack() {
        auto& storage=cache();
        for(size_t i=0;i<storage.values.size();++i) if(!storage.busy[i]) {
            slot=i;storage.busy[i]=true;break;
        }
    }
    ~V08LineStack() {
        if(slot<8) {
            auto& storage=cache();
            if(storage.values[slot].capacity()>4096) std::string().swap(storage.values[slot]);
            else storage.values[slot].clear();
            storage.busy[slot]=false;
        }
    }
    V08LineStack(const V08LineStack&)=delete;
    V08LineStack& operator=(const V08LineStack&)=delete;
    std::string& value() { return slot<8?cache().values[slot]:fallback; }
    static void appendExecution(std::string& text,unsigned long long execution) {
        char number[32];
        const auto formatted=std::to_chars(number,number+sizeof(number),execution);
        text+='/';text.append(number,static_cast<size_t>(formatted.ptr-number));
    }
};
#endif
