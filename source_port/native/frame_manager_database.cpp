// SPDX-License-Identifier: GPL-3.0-or-later
void SPELLframeManager::copyDatabase(const std::string& database, PyFrameObject* toFrame)
{
    if (!m_currentFrame || !toFrame) return;
    SPELLpython313::FrameGlobals source(m_currentFrame), target(toFrame);
    SPELLpython313::FrameLocals locals(toFrame);
    if (!source.get() || !target.get() || !locals.get()) SPELLpythonHelper::instance().checkError();
    PyObject* value = PyDict_GetItemString(source.get(), database.c_str()); // borrowed
    SPELLpython313::Owned fallback;
    if (!value) {
        SPELLpython313::Owned builtins(PyImport_ImportModule(BUILTINS));
        if (!builtins.get()) SPELLpythonHelper::instance().checkError();
        PyObject* object = nullptr;
        if (PyObject_GetOptionalAttrString(builtins.get(), database.c_str(), &object) < 0)
            SPELLpythonHelper::instance().checkError();
        fallback.reset(object);
        value = fallback.get();
    }
    if (!value) return;
    SPELLpython313::Owned key(PyUnicode_FromStringAndSize(database.data(), database.size()));
    if (!key.get() || PyDict_SetItem(target.get(), key.get(), value)<0
            || PyObject_SetItem(locals.get(), key.get(), value)<0)
        SPELLpythonHelper::instance().checkError();
}

//=============================================================================
