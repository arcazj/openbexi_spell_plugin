// SPDX-License-Identifier: GPL-3.0-or-later
// Public CPython 3.13 frame mappings replace removed fast-locals synchronization.
namespace {
using SPELLpython313::Owned;
std::string watchRepr(PyObject* value) {
    Owned result(PyObject_Repr(value));
    if (!result.get()) { PyErr_Clear(); return "<unprintable>"; }
    return SPELLpython313::text(result.get());
}
SPELLvariableMonitor::VarMap collectVariables(PyObject* mapping, bool global,
        const std::function<bool(const std::string&,PyObject*)>& discard) {
    // Repr can run user code and mutate the live namespace. Snapshot its entries
    // first, keeping their objects alive through formatting and notification.
    Owned snapshot(PyObject_CallOneArg(reinterpret_cast<PyObject*>(&PyDict_Type), mapping));
    if (!snapshot.get()) SPELLpythonHelper::instance().checkError();
    SPELLvariableMonitor::VarMap result;
    Py_ssize_t pos = 0;
    PyObject *key, *value;
    while (PyDict_Next(snapshot.get(), &pos, &key, &value)) {
        if (!PyUnicode_Check(key)) continue;
        std::string name = SPELLpython313::text(key);
        if (discard(name, value)) continue;
        result.emplace(name, SPELLvarInfo(name, SPELLpython313::text(reinterpret_cast<PyObject*>(Py_TYPE(value))),
                                          watchRepr(value), global));
    }
    return result;
}
void diffVariables(const SPELLvariableMonitor::VarMap& before, const SPELLvariableMonitor::VarMap& after,
        std::vector<SPELLvarInfo>& added, std::vector<SPELLvarInfo>& changed, std::vector<SPELLvarInfo>& deleted) {
    for (const auto& entry: after) {
        auto old = before.find(entry.first);
        if (old == before.end()) { auto info = entry.second; info.isAdded = true; added.push_back(info); }
        else if (old->second.varValue != entry.second.varValue || old->second.varType != entry.second.varType)
            changed.push_back(entry.second);
    }
    for (const auto& entry: before) {
        if (after.find(entry.first) == after.end()) {
            auto info = entry.second; info.isDeleted = true; deleted.push_back(info);
        }
    }
}
}

bool SPELLvariableMonitor::s_enabled = false;
SPELLvariableMonitor::SPELLvariableMonitor(SPELLvariableChangeListener* listener, PyFrameObject* frame,
        std::set<std::string>& initialVariables)
    : m_frame(frame), m_listener(listener), m_ignoreVariables(initialVariables)
{
    m_initialized = false;
    m_scopeName = PSTR(frame);
}
SPELLvariableMonitor::~SPELLvariableMonitor() { m_frame = nullptr; m_listener = nullptr; }
void SPELLvariableMonitor::retrieveGlobalVariables()
{
    Owned globals(PyFrame_GetGlobals(m_frame));
    if (!globals.get()) SPELLpythonHelper::instance().checkError();
    m_globalVariables = collectVariables(globals.get(), true,
        [this](const std::string& name, PyObject* value) { return shouldDiscard(name, value); });
}
void SPELLvariableMonitor::retrieveLocalVariables()
{
    Owned globals(PyFrame_GetGlobals(m_frame)), locals(PyFrame_GetLocals(m_frame));
    if (!globals.get() || !locals.get()) SPELLpythonHelper::instance().checkError();
    m_localVariables.clear();
    if (locals.get() != globals.get())
        m_localVariables = collectVariables(locals.get(), false,
            [this](const std::string& name, PyObject* value) { return shouldDiscard(name, value); });
}
std::vector<std::string> SPELLvariableMonitor::retrieveNames()
{
    SPELLpython313::GIL gil;
    Owned code(reinterpret_cast<PyObject*>(PyFrame_GetCode(m_frame)));
    if (!code.get()) SPELLpythonHelper::instance().checkError();
    std::set<std::string> names;
    for (const char* attribute: {"co_varnames", "co_freevars", "co_cellvars"}) {
        Owned values(PyObject_GetAttrString(code.get(), attribute));
        if (!values.get()) SPELLpythonHelper::instance().checkError();
        for (Py_ssize_t i = 0; i < PyTuple_Size(values.get()); ++i)
            names.insert(SPELLpython313::text(PyTuple_GetItem(values.get(), i)));
    }
    return {names.begin(), names.end()};
}
void SPELLvariableMonitor::initialize()
{
    if (m_initialized || !s_enabled) return;
    SPELLpython313::GIL gil;
    retrieveGlobalVariables();
    retrieveLocalVariables();
    m_initialized = true;
}
const SPELLvariableMonitor::VarMap& SPELLvariableMonitor::getGlobalVariables() { initialize(); return m_globalVariables; }
const SPELLvariableMonitor::VarMap& SPELLvariableMonitor::getLocalVariables() { initialize(); return m_localVariables; }
void SPELLvariableMonitor::changeVariable(SPELLvarInfo& var)
{
    SPELLpython313::GIL gil;
    initialize();
    auto& helper = SPELLpythonHelper::instance();
    Owned name(PyUnicode_DecodeUTF8(var.varName.data(), var.varName.size(), "strict"));
    if (!name.get()) helper.checkError();
    if (!PyUnicode_IsIdentifier(name.get()))
        THROW_EXCEPTION("Unable to change variable", "Name must be a Python identifier", SPELL_ERROR_PYTHON_API);
    Owned globals(PyFrame_GetGlobals(m_frame)), locals(PyFrame_GetLocals(m_frame));
    if (!globals.get() || !locals.get()) helper.checkError();
    if (var.varValue.find('\0') != std::string::npos)
        THROW_EXCEPTION("Unable to change variable", "Expression contains a null byte", SPELL_ERROR_PYTHON_API);
    Owned value((var.varValue.empty() || var.varValue == "<empty>") ? PyUnicode_FromString("") :
        PyRun_StringFlags(var.varValue.c_str(), Py_eval_input, globals.get(), locals.get(), nullptr));
    if (!value.get()) helper.checkError();
    PyObject* mapping = var.isGlobal ? globals.get() : locals.get();
    if (PyObject_SetItem(mapping, name.get(), value.get()) < 0) helper.checkError();
    var.varValue = watchRepr(value.get());
    var.varType = SPELLpython313::text(reinterpret_cast<PyObject*>(Py_TYPE(value.get())));
    analyze();
}
PyObject* SPELLvariableMonitor::getVariableRef(const std::string& name)
{
    SPELLpython313::GIL gil;
    Owned globals(PyFrame_GetGlobals(m_frame));
    if (!globals.get()) SPELLpythonHelper::instance().checkError();
    PyObject* value = PyDict_GetItemString(globals.get(), name.c_str());
    if (value) return value; // Original API returns a reference borrowed from the frame.
    Owned builtins(PyFrame_GetBuiltins(m_frame));
    if (!builtins.get()) SPELLpythonHelper::instance().checkError();
    return PyDict_GetItemString(builtins.get(), name.c_str());
}
void SPELLvariableMonitor::getVariable(SPELLvarInfo& var)
{
    initialize();
    // Resolve locals before globals, matching Python's shadowing rules.
    auto local = m_localVariables.find(var.varName);
    auto global = m_globalVariables.find(var.varName);
    if (local != m_localVariables.end()) var = local->second;
    else if (global != m_globalVariables.end()) var = global->second;
    else { var.varValue = "???"; var.varType = "???"; var.isGlobal = false; }
}
bool SPELLvariableMonitor::shouldDiscard(const std::string& name, PyObject* value)
{
    if (name == DatabaseConstants::SCDB || name == DatabaseConstants::GDB || name == DatabaseConstants::PROC
            || name == DatabaseConstants::ARGS || name == DatabaseConstants::IVARS
            || m_ignoreVariables.count(name) || name.substr(0,2) == "__") return true;
    if (PyCallable_Check(value) || PyType_Check(value) || PyModule_Check(value)) return true;
    // Watching ordinary objects must not import the database/driver framework.
    // When the original Database class is loaded, retain its existing exclusion.
    PyObject* module = PyDict_GetItemString(PyImport_GetModuleDict(), "spell.lib.adapter.databases.database");
    if (module && PyModule_Check(module)) {
        PyObject* cls = PyDict_GetItemString(PyModule_GetDict(module), "Database");
        if (cls) {
            int match = PyObject_IsInstance(value, cls);
            if (match < 0) SPELLpythonHelper::instance().checkError();
            if (match) return true;
        }
    }
    return false;
}
void SPELLvariableMonitor::analyze()
{
    if (!s_enabled) return;
    SPELLpython313::GIL gil;
    initialize();
    VarMap globalsBefore = m_globalVariables, localsBefore = m_localVariables;
    retrieveGlobalVariables();
    retrieveLocalVariables();
    std::vector<SPELLvarInfo> added, changed, deleted;
    diffVariables(globalsBefore, m_globalVariables, added, changed, deleted);
    diffVariables(localsBefore, m_localVariables, added, changed, deleted);
    if (m_listener && (!added.empty() || !changed.empty() || !deleted.empty()))
        m_listener->variableChanged(added, changed, deleted);
}
