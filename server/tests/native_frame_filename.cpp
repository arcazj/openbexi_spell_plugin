// SPDX-License-Identifier: GPL-3.0-or-later
#include "frame_filename.H"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static bool measuring=false;
static size_t allocated=0, allocations=0;
extern "C" void __sanitizer_malloc_hook(const volatile void*,size_t size) {
    if(measuring) {allocated+=size; ++allocations;}
}
static void require(bool ok) {if(!ok) throw std::runtime_error("frame filename invariant");}
static std::string oldName(PyFrameObject* frame) {
    PyObject* code=reinterpret_cast<PyObject*>(PyFrame_GetCode(frame));
    if(!code) return "<unavailable>";
    PyObject* name=PyObject_GetAttrString(code,"co_filename"); Py_DECREF(code);
    if(!name) return "<unavailable>";
    PyObject* rendered=PyObject_Str(name); Py_DECREF(name);
    if(!rendered) {PyErr_Clear();return "<unprintable>";}
    Py_ssize_t size=0; const char* data=PyUnicode_AsUTF8AndSize(rendered,&size);
    if(!data) {PyErr_Clear();Py_DECREF(rendered);return "<unprintable>";}
    std::string result(data,size); Py_DECREF(rendered); return result;
}
namespace SPELLpython313 {static std::string filename(PyFrameObject* frame) {return oldName(frame);}}
struct BeforeFilter {std::string m_procPath,m_libPath;
    int apply(PyFrameObject* frame) {
#include "filename_filter_before.inc"
        return 1;
    }
};
struct AfterFilter {std::string m_procPath,m_libPath;
    int apply(PyFrameObject* frame) {
#include "filename_filter_after.inc"
        (void)file;
        return 1;
    }
};
static PyFrameObject* newFrame(PyObject* filename) {
    PyObject* code=Py_CompileString("x=1\n","placeholder",Py_file_input);require(code);
    PyObject* replace=PyObject_GetAttrString(code,"replace");require(replace);
    PyObject* empty=PyTuple_New(0);PyObject* kwargs=PyDict_New();require(empty&&kwargs);
    require(PyDict_SetItemString(kwargs,"co_filename",filename)==0);
    PyObject* changed=PyObject_Call(replace,empty,kwargs);require(changed);
    Py_DECREF(kwargs);Py_DECREF(empty);Py_DECREF(replace);Py_DECREF(code);
    PyObject* globals=PyDict_New();require(globals);
    PyFrameObject* frame=PyFrame_New(PyThreadState_Get(),reinterpret_cast<PyCodeObject*>(changed),globals,nullptr);
    Py_DECREF(changed);Py_DECREF(globals);require(frame);return frame;
}
int main() {
    Py_Initialize(); size_t before=0,after=0,beforeCalls=0,afterCalls=0,checks=0;
    size_t acceptedBefore=0,acceptedAfter=0;
    for (const char* path:{"/source/long/procedure.py",u8"/library/é中🙂/very-long-name.py","<dynamic-generated-code>"}) {
        PyObject* filename=PyUnicode_FromString(path);require(filename);
        PyFrameObject* frame=newFrame(filename);
        {V08FrameFilename name(frame);require(name.view()==oldName(frame));}
        const auto refs=Py_REFCNT(filename);
        for (const std::string proc:{"/source","absent",""}) for (const std::string lib:{"/library","absent",""}) {
            require(BeforeFilter{proc,lib}.apply(frame)==AfterFilter{proc,lib}.apply(frame));++checks;
        }
        allocated=allocations=0; measuring=true;
        for(int n=0;n<10000;++n) {auto name=oldName(frame);require(name==path);}
        measuring=false; before+=allocated;beforeCalls+=allocations;
        allocated=allocations=0; measuring=true;
        for(int n=0;n<10000;++n) {V08FrameFilename name(frame);require(name.view()==path);}
        measuring=false;after+=allocated;afterCalls+=allocations;
        BeforeFilter oldAccepted{"",""};AfterFilter newAccepted{"",""};
        allocated=allocations=0;measuring=true;
        for(int n=0;n<10000;++n)require(oldAccepted.apply(frame)==1);
        measuring=false;acceptedBefore+=allocations;
        allocated=allocations=0;measuring=true;
        for(int n=0;n<10000;++n)require(newAccepted.apply(frame)==1);
        measuring=false;acceptedAfter+=allocations;
        require(Py_REFCNT(filename)==refs);
        // Nested owners do not overwrite one another. A view survives its frame.
        {V08FrameFilename outer(frame);const auto& owned=outer.owned();
         {V08FrameFilename inner(frame);require(inner.owned()==owned);}
         PyThreadState* state=PyEval_SaveThread();require(outer.view()==path&&owned==path);PyEval_RestoreThread(state);
         Py_DECREF(frame);Py_DECREF(filename);require(outer.view()==path&&owned==path);}
    }
    // co_filename can contain embedded NUL; use its length, never strlen.
    const char nulName[]="/source/a\0/library/b.py";
    PyObject* filename=PyUnicode_DecodeUTF8(nulName,sizeof(nulName)-1,"strict");require(filename);
    PyFrameObject* frame=newFrame(filename);Py_DECREF(filename);
    {V08FrameFilename name(frame);require(name.view()==oldName(frame));require(name.view().size()==sizeof(nulName)-1);
     require(BeforeFilter{"missing","/library"}.apply(frame)==AfterFilter{"missing","/library"}.apply(frame));++checks;}
    Py_DECREF(frame);
    // Match the historical conversion-error fallback and exception clearing.
    filename=PyUnicode_FromOrdinal(0xd800);require(filename);frame=newFrame(filename);Py_DECREF(filename);
    {auto old=oldName(frame);V08FrameFilename name(frame);require(old=="<unprintable>"&&name.view()==old&&!PyErr_Occurred());}
    Py_DECREF(frame);
    require(acceptedBefore>=30000&&acceptedAfter==0);
    // More simultaneous owners than cached slots must keep distinct snapshots.
    std::vector<V08FrameFilename*> owners;
    std::vector<std::string> names;
    for(int i=0;i<16;++i) {
        names.push_back("/nested/long-procedure-path/"+std::to_string(i)+".py");
        PyObject* value=PyUnicode_FromString(names.back().c_str());require(value);
        auto frame=newFrame(value);Py_DECREF(value);
        owners.push_back(new V08FrameFilename(frame));Py_DECREF(frame);
        require(owners.back()->owned()==names.back());
    }
    for(size_t i=0;i<owners.size();++i)require(owners[i]->owned()==names[i]);
    {std::string large(100000,'x');PyObject* value=PyUnicode_FromString(large.c_str());require(value);
     auto frame=newFrame(value);Py_DECREF(value);V08FrameFilename name(frame);Py_DECREF(frame);
     require(name.owned()==large);}
    for(size_t i=0;i<owners.size();++i){require(owners[i]->owned()==names[i]);delete owners[i];}
    Py_Finalize();std::cout<<"{\"passed\":true,\"lookups\":30000,\"accepted_before_allocations\":"<<acceptedBefore
        <<",\"accepted_after_allocations\":"<<acceptedAfter<<",\"filter_cases\":"<<checks
        <<",\"before_bytes\":"<<before<<",\"after_bytes\":"<<after
        <<",\"before_allocations\":"<<beforeCalls<<",\"after_allocations\":"<<afterCalls<<"}\n";
}
