// SPDX-License-Identifier: GPL-3.0-or-later
void SPELLbytecode::analyze()
{
    SPELLpython313::GIL gil;
    using SPELLpython313::Owned;
    auto& helper = SPELLpythonHelper::instance();
    Owned description(SPELLanalysis313::describe(m_code));
    PyObject *rows, *blocks;
    if (!PyArg_ParseTuple(description.get(), "OOii", &rows, &blocks, &m_lastAddr, &m_lastLine)) helper.checkError();
    for (Py_ssize_t index = 0; index < PyList_Size(rows); ++index) {
        Owned row(PySequence_Tuple(PyList_GetItem(rows, index)));
        BLine info;
        int executable, keep, returns;
        if (!row.get() || !PyArg_ParseTuple(row.get(), "IIIppp", &info.lineno, &info.offset, &info.opcode,
                                           &executable, &keep, &returns)) helper.checkError();
        info.executable = executable; info.keepWithNext = keep; info.returnConst = returns;
        m_lines.push_back(info);
    }
    for (Py_ssize_t index = 0; index < PyList_Size(blocks); ++index) {
        TryBlock info{};
        PyObject *handlers, *final;
        if (!PyArg_ParseTuple(PyList_GetItem(blocks,index), "IIIIOO", &info.try_lineno, &info.body_lineno,
                &info.end_try_lineno, &info.end_lineno, &handlers, &final)) helper.checkError();
        if (!PyArg_ParseTuple(final, "II", &info.finally_lineno, &info.finally_end_lineno)) helper.checkError();
        for (Py_ssize_t n = 0; n < PyList_Size(handlers); ++n) {
            unsigned int first, last;
            if (!PyArg_ParseTuple(PyList_GetItem(handlers,n), "II", &first, &last)) helper.checkError();
            info.except_ranges.emplace_back(first,last);
        }
        if (!info.except_ranges.empty()) {
            info.except_lineno = info.except_ranges.front().first;
            info.end_except_lineno = info.except_ranges.back().second;
        }
        m_tryBlocks.push_back(info);
    }
    helper.checkError();
}
