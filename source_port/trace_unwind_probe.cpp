// SPDX-License-Identifier: GPL-3.0-or-later
// Isolates trace exception unwinding from SPELL and its native port.
#include <Python.h>
#include <frameobject.h>
#include <cstdio>
static int count=0;
static int trace(PyObject*,PyFrameObject* frame,int what,PyObject*) {
    if (what==PyTrace_LINE && PyFrame_GetLineNumber(frame)==3 && ++count==5) {
        fprintf(stderr,"TRACE_STOP %d\n",PyFrame_GetLineNumber(frame));
        PyErr_SetString(PyExc_RuntimeError,"stop");
        PyObject* pending=PyErr_GetRaisedException();
        PyEval_SetTrace(nullptr,nullptr);
        PyErr_SetRaisedException(pending);
        return -1;
    }
    return 0;
}
int main() {
    Py_Initialize();
    PyRun_SimpleString("import time,dis; finalized=[]");
    PyRun_SimpleString("def f():\n    try:\n        while True: time.sleep(.001)\n    finally:\n        finalized.append('closed')\n");
    PyRun_SimpleString("dis.dis(f)");
    PyEval_SetTrace(trace,nullptr);
    int result=PyRun_SimpleString("f()\n");
    fprintf(stderr,"EVALUATOR_RESULT %d\n",result);
    PyEval_SetTrace(nullptr,nullptr);
    PyRun_SimpleString("import sys\nseen=0\ndef tracer(frame,event,arg):\n    global seen\n    if frame.f_code is f.__code__ and event=='line':\n        seen+=1\n        if seen==5: raise RuntimeError('python stop')\n    return tracer\nsys.settrace(tracer)\ntry: f()\nexcept RuntimeError: pass\nfinally: sys.settrace(None)\nprint('PYTHON_TRACER_DONE',sys.version,flush=True)\n");
    PyObject* globals=PyModule_GetDict(PyImport_AddModule("__main__"));
    const Py_ssize_t finalized=PyList_Size(PyDict_GetItemString(globals,"finalized"));
    fprintf(stdout,"TRACE_UNWIND_CHECKS %zd/2\n",finalized);
    Py_FinalizeEx();
    return finalized==2 ? 0 : 1;
}
