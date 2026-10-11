// SPDX-License-Identifier: GPL-3.0-or-later
#include <cstdlib>
void SPELLpythonHelper::initialize()
{
    if (m_initialized) return;
    if (m_frameworkRetired)
        THROW_EXCEPTION("Cannot reinitialize the full SPELL framework", "Start a fresh executor process for the RPC framework", SPELL_ERROR_PYTHON_API);
    if (!Py_IsInitialized()) {
        PyConfig config;
        PyConfig_InitIsolatedConfig(&config);
        config.buffered_stdio = 0;
        // The installed launcher selects its own isolated virtual environment.
        // PyConfig ignores PYTHONPATH/PYTHONHOME; never fall back to the build's
        // site-packages when a runtime environment was explicitly selected.
        PyStatus status = PyStatus_Ok();
        if (const char* interpreter = std::getenv("OPENBEXI_SPELL_PYTHON")) {
            status = PyConfig_SetBytesString(&config,&config.program_name,interpreter);
            if (!PyStatus_Exception(status))
                status = PyConfig_SetBytesString(&config,&config.executable,interpreter);
        }
        if (!PyStatus_Exception(status)) status = Py_InitializeFromConfig(&config);
        std::string error = PyStatus_Exception(status)
            ? (status.err_msg ? status.err_msg : "Python initialization failed") : "";
        PyConfig_Clear(&config);
        if (!error.empty())
            THROW_EXCEPTION("Unable to initialize", error, SPELL_ERROR_PYTHON_API);
        m_ownsInterpreter = true;
        m_ownerThread = std::this_thread::get_id();
    }
    m_initialized = true;
    if (m_ownsInterpreter) m_embeddedThread = PyEval_SaveThread();
}

void SPELLpythonHelper::loadFramework()
{
    // The selected interpreter supplies installed packages. Procedures import
    // their symbols explicitly; no SPELL names are inserted into builtins.
    SPELLpython313::GIL gil;
    m_frameworkLoaded = true;
    const char* modules[] = {"spell.lang.functions", "spell.lang.constants",
        "spell.lang.modifiers", "spell.lang.user", "spell.lib.adapter.utctime",
        "spell.lib.adapter.file", "libSPELL_DTA_v3"};
    for (const char* name: modules) {
        importAllFrom(name);
    }
}

void SPELLpythonHelper::finalize()
{
    if (!m_initialized) return;
    if (m_ownsInterpreter) {
        if (std::this_thread::get_id() != m_ownerThread)
            THROW_EXCEPTION("Cannot finalize Python", "Only the owning thread may finalize", SPELL_ERROR_PYTHON_API);
        PyEval_RestoreThread(m_embeddedThread);
        m_embeddedThread = nullptr;
        Py_FinalizeEx();
        m_frameworkRetired = m_frameworkLoaded;
        m_frameworkLoaded = false;
        m_ownsInterpreter = false;
    }
    m_initialized = false;
}

void SPELLpythonHelper::addToPath(const std::string& path)
{
    SPELLpython313::GIL gil;
    PyObject* paths = PySys_GetObject("path"); // borrowed
    SPELLpython313::Owned item(PyUnicode_DecodeFSDefaultAndSize(path.data(), path.size()));
    if (!paths || !item.get()) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError, "sys.path is unavailable");
        checkError();
    }
    int present = PySequence_Contains(paths, item.get());
    if (present < 0 || (!present && PyList_Append(paths, item.get()) < 0)) checkError();
}
