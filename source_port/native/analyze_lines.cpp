// SPDX-License-Identifier: GPL-3.0-or-later
void SPELLlnotab::analyze(PyCodeObject* code)
{
    SPELLpython313::GIL gil;
    using SPELLpython313::Owned;
    auto& helper = SPELLpythonHelper::instance();
    Owned ranges(PyObject_CallMethod(reinterpret_cast<PyObject*>(code), "co_lines", nullptr));
    if (!ranges.get()) helper.checkError();
    int previous = -1;
    while (PyObject* next = PyIter_Next(ranges.get())) {
        Owned range(next);
        int start, end;
        PyObject* line;
        if (!PyArg_ParseTuple(range.get(), "iiO", &start, &end, &line)) helper.checkError();
        if (start == end) continue;
        if (line == Py_None) { previous = -1; continue; }
        long number = PyLong_AsLong(line);
        helper.checkError();
        // Line zero is the module RESUME instruction, not a source line.
        if (number > 0 && number != previous) {
            m_lines.push_back(number);
            m_addrs.push_back(start);
        }
        previous = number;
    }
    helper.checkError();
}
