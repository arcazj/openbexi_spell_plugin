// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_FRAME_FILENAME_H
#define OPENBEXI_V08_FRAME_FILENAME_H
#include <Python.h>
#include <frameobject.h>
#include <array>
#include <string>
#include <string_view>

// A dispatch-scoped Unicode owner, not a persistent cache. Hold the rendered
// object while borrowing UTF-8 bytes. Construction/destruction require the GIL;
// the pinned immutable bytes remain valid across nested calls and GIL release.
class V08FrameFilename {
    PyObject* rendered=nullptr;
    std::string_view bytes="<unavailable>";
    // Accepted procedure frames still need std::string APIs. Each active
    // dispatch owns a distinct slot, including nested calls across GIL release.
    // Keep at most eight ordinary filename buffers per native thread. Larger
    // names and deeper nesting retain ordinary scope-local ownership.
    struct Copies {
        std::array<std::string,8> values;
        std::array<bool,8> busy{};
    };
    static Copies& copies() { static thread_local Copies value; return value; }
    std::string fallback;
    std::string* copy=nullptr;
    size_t slot=8;
public:
    explicit V08FrameFilename(PyFrameObject* frame) {
        PyObject* code=reinterpret_cast<PyObject*>(PyFrame_GetCode(frame));
        if (!code) return;
        PyObject* name=PyObject_GetAttrString(code,"co_filename");
        Py_DECREF(code);
        if (!name) return;
        rendered=PyObject_Str(name);
        Py_DECREF(name);
        if (!rendered) { PyErr_Clear(); bytes="<unprintable>"; return; }
        Py_ssize_t size=0;
        const char* data=PyUnicode_AsUTF8AndSize(rendered,&size);
        if (!data) { PyErr_Clear(); bytes="<unprintable>"; return; }
        bytes=std::string_view(data,static_cast<size_t>(size));
    }
    ~V08FrameFilename() {
        if(slot<8) {
            auto& cache=copies();
            if(cache.values[slot].capacity()>4096) std::string().swap(cache.values[slot]);
            else cache.values[slot].clear();
            cache.busy[slot]=false;
        }
        Py_XDECREF(rendered);
    }
    V08FrameFilename(const V08FrameFilename&)=delete;
    V08FrameFilename& operator=(const V08FrameFilename&)=delete;
    std::string_view view() const { return bytes; }
    const std::string& owned() {
        if(!copy) {
            auto* target=&fallback;
            if(bytes.size()<=4096) {
                auto& cache=copies();
                for(size_t i=0;i<cache.values.size();++i) if(!cache.busy[i]) {
                    slot=i;cache.busy[i]=true;target=&cache.values[i];break;
                }
            }
            // assign may throw; this object's destructor still releases a
            // reserved slot. No borrowed reference leaves this dispatch.
            try { target->assign(bytes.data(),bytes.size()); }
            catch(...) {
                if(slot<8) copies().busy[slot]=false;
                slot=8;
                throw;
            }
            copy=target;
        }
        return *copy;
    }
};
#endif
