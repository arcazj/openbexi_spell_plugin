// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef SPELL_CONTINUATION_CODEC_H
#define SPELL_CONTINUATION_CODEC_H
#include "SPELL_UTIL/SPELLpython313.H"
#include "SPELL_UTIL/SPELLpythonHelper.H"
#include "SPELL_WS/SPELLwsStorage.H"
#include "SPELL_WS/SPELLcontinuationSource.H"
#include <fstream>
#include <iterator>
#include <memory>
#include <unistd.h>
#include <fcntl.h>
namespace SPELLcontinuationCodec {
inline PyObject* module() {
    PyObject* modules = PyImport_GetModuleDict();
    PyObject* existing = PyDict_GetItemString(modules, "_spell_continuation_codec");
    if (existing) {
        if (!PyModule_Check(existing)) {
            PyErr_SetString(PyExc_ImportError, "invalid continuation codec module");
            SPELLpythonHelper::instance().checkError();
        }
        return Py_NewRef(existing);
    }
    SPELLpython313::Owned created(PyModule_New("_spell_continuation_codec"));
    if (!created.get()) SPELLpythonHelper::instance().checkError();
    PyObject* globals = PyModule_GetDict(created.get());
    SPELLpython313::Owned identity(PyUnicode_FromString(continuationSourceIdentity));
    if (!identity.get() || PyDict_SetItemString(globals,"_source_identity",identity.get())<0
        || PyDict_SetItemString(globals,"__builtins__",PyEval_GetBuiltins())<0)
        SPELLpythonHelper::instance().checkError();
    SPELLpython313::Owned result(PyRun_StringFlags(continuationSource,Py_file_input,globals,globals,nullptr));
    if (!result.get() || PyDict_SetItemString(modules,"_spell_continuation_codec",created.get())<0)
        SPELLpythonHelper::instance().checkError();
    return Py_NewRef(created.get());
}
inline PyObject* source(const std::string& filename) {
    std::ifstream stream(filename, std::ios::binary);
    if (!stream) THROW_EXCEPTION("Cannot checkpoint procedure", "Source is unavailable: " + filename, SPELL_ERROR_WSTART);
    std::string bytes((std::istreambuf_iterator<char>(stream)),std::istreambuf_iterator<char>());
    PyObject* result = PyBytes_FromStringAndSize(bytes.data(),bytes.size());
    if (!result) SPELLpythonHelper::instance().checkError();
    return result;
}
inline void write(const std::string& filename, const std::string& procedure, PyObject* state) {
    SPELLpython313::Owned codec(module()), bytes(source(procedure));
    SPELLpython313::Owned encoded(PyObject_CallMethod(codec.get(),"encode","OO",bytes.get(),state));
    if (!encoded.get()) SPELLpythonHelper::instance().checkError();
    // A fresh file is committed only after the complete graph and stream close.
    std::string temporary = filename + ".XXXXXX";
    int descriptor = mkstemp(temporary.data());
    if (descriptor < 0) THROW_EXCEPTION("Cannot checkpoint procedure", "Temporary file creation failed", SPELL_ERROR_FILESYSTEM);
    close(descriptor);
    try {
        {
            SPELLwsStorage storage(temporary,SPELLwsStorage::MODE_WRITE);
            storage.storeObject(PyTuple_GetItem(encoded.get(),0));
            storage.storeObject(PyTuple_GetItem(encoded.get(),1));
        }
        descriptor = open(temporary.c_str(),O_RDONLY);
        int flushed = descriptor < 0 ? -1 : fsync(descriptor);
        if (descriptor >= 0) close(descriptor);
        if (flushed < 0 || rename(temporary.c_str(),filename.c_str()) != 0)
            THROW_EXCEPTION("Cannot checkpoint procedure", "Atomic checkpoint commit failed", SPELL_ERROR_FILESYSTEM);
        auto slash = filename.find_last_of('/');
        std::string parent = slash == std::string::npos ? "." : filename.substr(0,slash);
        if (parent.empty()) parent = "/";
        descriptor = open(parent.c_str(),O_RDONLY|O_DIRECTORY);
        flushed = descriptor < 0 ? -1 : fsync(descriptor);
        if (descriptor >= 0) close(descriptor);
        if (flushed < 0) THROW_EXCEPTION("Cannot checkpoint procedure", "Checkpoint committed but directory sync failed", SPELL_ERROR_FILESYSTEM);
    } catch (...) {
        unlink(temporary.c_str()); unlink((temporary+"_WRITE").c_str()); throw;
    }
    unlink((temporary+"_WRITE").c_str());
}
inline PyObject* read(const std::string& filename, const std::string& procedure) {
    SPELLwsStorage storage(filename,SPELLwsStorage::MODE_READ);
    SPELLpython313::Owned metadata(storage.loadObject()), payload(storage.loadObject());
    SPELLpython313::Owned codec(module()), bytes(source(procedure));
    PyObject* result = PyObject_CallMethod(codec.get(),"decode","OOO",bytes.get(),metadata.get(),payload.get());
    if (!result) SPELLpythonHelper::instance().checkError();
    return result;
}
}
#endif
