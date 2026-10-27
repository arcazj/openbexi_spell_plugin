// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_FRAME_FILENAME_H
#define OPENBEXI_V08_FRAME_FILENAME_H
#include <Python.h>
#include <frameobject.h>
#include <string_view>

// A dispatch-scoped Unicode owner, not a persistent cache. Hold the rendered
// object while borrowing UTF-8 bytes. Construction/destruction require the GIL;
// the pinned immutable bytes remain valid across nested calls and GIL release.
class V08FrameFilename {
    PyObject* rendered=nullptr;
    std::string_view bytes="<unavailable>";
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
    ~V08FrameFilename() { Py_XDECREF(rendered); }
    V08FrameFilename(const V08FrameFilename&)=delete;
    V08FrameFilename& operator=(const V08FrameFilename&)=delete;
    std::string_view view() const { return bytes; }
};
#endif
