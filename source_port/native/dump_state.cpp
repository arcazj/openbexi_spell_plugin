// SPDX-License-Identifier: GPL-3.0-or-later
void SPELLutils::dumpInterpreterInfo(const std::string& id)
{
    SPELLpython313::GIL gil;
    int interpreter = 0;
    for (PyInterpreterState* state = PyInterpreterState_Head(); state;
         state = PyInterpreterState_Next(state), ++interpreter) {
        std::ofstream out(getSPELL_DATA() + PATH_SEPARATOR + "Runtime" + PATH_SEPARATOR
            + id + "_interpreter_state_" + ISTR(interpreter) + ".dump");
        out << "Interpreter ID: " << PyInterpreterState_GetID(state) << '\n';
        int thread = 0;
        for (PyThreadState* current = PyInterpreterState_ThreadHead(state); current;
             current = PyThreadState_Next(current), ++thread)
            dumpThreadStateInfo(id, current, interpreter, thread);
        out << "Thread states: " << thread << '\n';
    }
}

void SPELLutils::dumpThreadStateInfo(const std::string& id, PyThreadState* ts,
                                    int iStateId, int TStateId)
{
    std::ofstream out(getSPELL_DATA() + PATH_SEPARATOR + "Runtime" + PATH_SEPARATOR
        + id + "_thread_state_" + ISTR(iStateId) + "." + ISTR(TStateId) + ".dump");
    out << "Thread state ID: " << PyThreadState_GetID(ts) << '\n';
    out << "Interpreter ID: " << PyInterpreterState_GetID(PyThreadState_GetInterpreter(ts)) << '\n';
    int count = 0;
    PyFrameObject* frame = PyThreadState_GetFrame(ts);
    while (frame) {
        SPELLpython313::Owned owner(reinterpret_cast<PyObject*>(frame));
        dumpFrameInfo(id, frame, iStateId, TStateId, count++);
        frame = PyFrame_GetBack(frame);
    }
    out << "Number of frames: " << count << '\n';
}

void SPELLutils::dumpFrameInfo(const std::string& id, PyFrameObject* frame,
                               int iStateId, int TStateId, int FrameId)
{
    std::ofstream out(getSPELL_DATA() + PATH_SEPARATOR + "Runtime" + PATH_SEPARATOR
        + id + "_frame_state_" + ISTR(iStateId) + "." + ISTR(TStateId)
        + "." + ISTR(FrameId) + ".dump");
    out << "Filename: " << SPELLpython313::filename(frame) << '\n';
    out << "Last line: " << PyFrame_GetLineNumber(frame) << '\n';
    out << "Last instruction: " << PyFrame_GetLasti(frame) << '\n';
    out << "Internal value/exception stacks: not exposed by the public CPython API\n";
}

