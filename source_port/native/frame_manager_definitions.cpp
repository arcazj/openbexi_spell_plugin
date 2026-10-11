// SPDX-License-Identifier: GPL-3.0-or-later
void SPELLframeManager::updateDefinitions(PyFrameObject* source, PyFrameObject* target)
{
    if (!m_definitions || !source || !target) return;
    SPELLpython313::FrameGlobals from(source), to(target);
    if (!from.get() || !to.get()) SPELLpythonHelper::instance().checkError();
    for (Py_ssize_t index=0; index<PyList_Size(m_definitions); ++index) {
        PyObject* key = PyList_GetItem(m_definitions, index); // borrowed
        std::string name = SPELLpython313::text(key);
        if (name == "ARGS" || name == "IVARS" || name == "__name__") continue;
        int contains = PyDict_Contains(to.get(), key);
        if (contains < 0) SPELLpythonHelper::instance().checkError();
        if (!contains) {
            PyObject* value = PyDict_GetItemWithError(from.get(), key); // borrowed
            if (!value && PyErr_Occurred()) SPELLpythonHelper::instance().checkError();
            if (value && PyDict_SetItem(to.get(), key, value)<0) SPELLpythonHelper::instance().checkError();
        }
    }
}

//=============================================================================
