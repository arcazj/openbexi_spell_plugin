// SPDX-License-Identifier: GPL-3.0-or-later
// Static label analysis only. Runtime Goto still resolves its argument through
// the original executor; dynamic expressions must never become guessed labels.
void SPELLgoto::analyze()
{
    SPELLpython313::GIL gil;
    using SPELLpython313::Owned;
    auto& helper = SPELLpythonHelper::instance();
    m_initLine = -1;
    Owned dis(PyImport_ImportModule("dis"));
    if (!dis.get()) helper.checkError();
    Owned getInstructions(PyObject_GetAttrString(dis.get(), "get_instructions"));
    if (!getInstructions.get()) helper.checkError();
    Owned instructions(PyObject_CallOneArg(getInstructions.get(), reinterpret_cast<PyObject*>(m_code)));
    if (!instructions.get()) helper.checkError();
    std::string candidate;
    std::vector<std::string> arguments;
    while (PyObject* next = PyIter_Next(instructions.get())) {
        Owned instruction(next);
        Owned opname(PyObject_GetAttrString(instruction.get(), "opname"));
        Owned argval(PyObject_GetAttrString(instruction.get(), "argval"));
        Owned target(PyObject_GetAttrString(instruction.get(), "is_jump_target"));
        if (!opname.get() || !argval.get() || !target.get()) helper.checkError();
        std::string op = SPELLpython313::text(opname.get());
        int branchTarget = PyObject_IsTrue(target.get());
        if (branchTarget < 0) helper.checkError();
        if (branchTarget) { candidate.clear(); arguments.clear(); }
        if (op == "LOAD_NAME" || op == "LOAD_GLOBAL") {
            candidate = SPELLpython313::text(argval.get());
            if (candidate != "Step" && candidate != "Goto") candidate.clear();
            arguments.clear();
        } else if (!candidate.empty() && op == "LOAD_CONST" && PyUnicode_Check(argval.get())) {
            Py_ssize_t size;
            const char* value = PyUnicode_AsUTF8AndSize(argval.get(), &size);
            if (!value) helper.checkError();
            arguments.emplace_back(value, size);
        } else if (op == "PUSH_NULL" || op == "EXTENDED_ARG") {
            // dis resolves the LOAD_GLOBAL name and EXTENDED_ARG operands.
        } else if (op == "CALL") {
            long arity = PyLong_AsLong(argval.get());
            helper.checkError();
            if ((candidate == "Step" && arity == 2 && arguments.size() == 2)
                    || (candidate == "Goto" && arity == 1 && arguments.size() == 1)) {
                Owned offsetObject(PyObject_GetAttrString(instruction.get(), "offset"));
                if (!offsetObject.get()) helper.checkError();
                long offset = PyLong_AsLong(offsetObject.get());
                helper.checkError();
                int line = PyCode_Addr2Line(m_code, offset);
                if (line > 0 && candidate == "Step") {
                    m_labels.insert(std::make_pair(arguments[0], line));
                    m_labelLines.insert(line);
                    m_titles.insert(std::make_pair(arguments[1], arguments[0]));
                    if (arguments[0] == "INIT") m_initLine = line;
                } else if (line > 0) {
                    m_gotos.insert(std::make_pair(line, arguments[0]));
                }
            }
            candidate.clear();
            arguments.clear();
        } else {
            // Do not carry a literal from an unrelated or dynamic expression
            // into a later call. The old scanner could fabricate such labels.
            candidate.clear();
            arguments.clear();
        }
    }
    helper.checkError();
}
