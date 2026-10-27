// SPDX-License-Identifier: GPL-3.0-or-later
#include <atomic>
#include <cassert>
#include <cstddef>
#include <iostream>
#include <string>
#include <thread>

// Collaborator fixture: original class bodies call this same release/restore
// API. State tokens and strict LIFO order are checked on each executing thread.
struct PyThreadState { int depth; };
class SPELLpythonHelper {
public:
    static thread_local int depth;
    static thread_local PyThreadState states[8];
    static SPELLpythonHelper& instance() { static SPELLpythonHelper helper; return helper; }
    PyThreadState* beginSafeAllowThreads() {
        assert(depth < 8); auto* state=&states[depth];state->depth=depth; ++depth;return state;
    }
    void endSafeAllowThreads(PyThreadState* state) {
        assert(depth>0 && state==&states[depth-1] && state->depth==depth-1); --depth;
    }
};
thread_local int SPELLpythonHelper::depth=0;
thread_local PyThreadState SPELLpythonHelper::states[8]{};
#include "before.inc"
#include "after.inc"

static std::atomic<bool> recording{false};
static std::atomic<size_t> allocations{0}, bytes{0};
extern "C" int __sanitizer_install_malloc_and_free_hooks(
    void (*)(const volatile void*, size_t), void (*)(const volatile void*));
static void allocated(const volatile void*, size_t n) {
    if(recording.load()) {++allocations; bytes+=n;}
}
static void freed(const volatile void*) {}
template<class Monitor> void semantics() {
    const std::string dynamic(100,'x');
    try {
        Monitor outer("SPELLexecutorImpl::dispatch()");
        assert(SPELLpythonHelper::depth==1);
        { Monitor inner(dynamic); assert(SPELLpythonHelper::depth==2); }
        assert(SPELLpythonHelper::depth==1);
        throw 1;
    } catch(int) { assert(SPELLpythonHelper::depth==0); }
}
template<class Monitor> size_t benchmark() {
    allocations=0;bytes=0;recording=true;
    for(int i=0;i<10000;++i) {Monitor monitor("SPELLexecutorImpl::dispatch()");}
    recording=false;assert(SPELLpythonHelper::depth==0);return allocations.load();
}
int main() {
    assert(__sanitizer_install_malloc_and_free_hooks(allocated,freed)>0);
    semantics<Before>();semantics<After>();
    std::thread a([]{for(int i=0;i<1000;++i)semantics<Before>();});
    std::thread b([]{for(int i=0;i<1000;++i)semantics<After>();});
    a.join();b.join();
    auto before=benchmark<Before>();auto beforeBytes=bytes.load();
    auto after=benchmark<After>();
    std::cout << "{\"semantics_passed\":true,\"same_size\":" << (sizeof(Before)==sizeof(After)?"true":"false")
              << ",\"before_allocations\":" << before << ",\"before_bytes\":" << beforeBytes
              << ",\"after_allocations\":" << after << ",\"after_bytes\":" << bytes << "}\n";
}
