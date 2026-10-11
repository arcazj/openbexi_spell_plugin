// SPDX-License-Identifier: GPL-3.0-or-later
// Preserve the original analyzer's bracket-continuation contract using the
// supported tokenizer. The compiler validates syntax before tokenization.
void SPELLastAnalyzer::process(const std::string& filename)
{
    SPELLpython313::GIL gil;
    using SPELLpython313::Owned;
    auto& helper = SPELLpythonHelper::instance();
    // A failed parse must not expose a previous procedure's classification.
    m_currentNode = NodeInfo{};
    std::string source = helper.readProcedureFile(filename);
    if (source.empty())
        THROW_EXCEPTION("Unable to parse script", "Cannot read source code", SPELL_ERROR_PYTHON_API);
    if (source.find('\0') != std::string::npos) {
        PyErr_SetString(PyExc_SyntaxError, "source code cannot contain null bytes");
        helper.checkError();
    }
    PyCompilerFlags flags{};
    flags.cf_flags = PyCF_ONLY_AST;
    flags.cf_feature_version = PY_MINOR_VERSION;
    Owned syntax(Py_CompileStringExFlags(source.c_str(), filename.c_str(), Py_file_input, &flags, -1));
    if (!syntax.get()) helper.checkError();
    Owned io(PyImport_ImportModule("io"));
    if (!io.get()) helper.checkError();
    Owned factory(PyObject_GetAttrString(io.get(), "StringIO"));
    if (!factory.get()) helper.checkError();
    Owned text(PyUnicode_DecodeUTF8(source.data(), source.size(), "strict"));
    if (!text.get()) helper.checkError();
    Owned stream(PyObject_CallOneArg(factory.get(), text.get()));
    if (!stream.get()) helper.checkError();
    Owned readline(PyObject_GetAttrString(stream.get(), "readline"));
    if (!readline.get()) helper.checkError();
    Owned tokenizer(PyImport_ImportModule("tokenize"));
    if (!tokenizer.get()) helper.checkError();
    Owned generate(PyObject_GetAttrString(tokenizer.get(), "generate_tokens"));
    Owned op(PyObject_GetAttrString(tokenizer.get(), "OP"));
    if (!generate.get() || !op.get()) helper.checkError();
    const long opType = PyLong_AsLong(op.get());
    helper.checkError();
    Owned tokens(PyObject_CallOneArg(generate.get(), readline.get()));
    if (!tokens.get()) helper.checkError();
    NodeInfo info{};
    // Include blank/comment lines so a continuation cannot accidentally be
    // offered as a separate execution line. Reserve a sentinel after EOF.
    info.maxLineNo = static_cast<unsigned int>(std::count(source.begin(), source.end(), '\n')) + 2;
    for (unsigned int n = 1; n < info.maxLineNo; ++n) info.lineTypes[n] = NONE;
    unsigned int depth = 0, opening = 0;
    while (PyObject* next = PyIter_Next(tokens.get())) {
        Owned token(next);
        Owned type(PyObject_GetAttrString(token.get(), "type"));
        if (!type.get()) helper.checkError();
        long tokenType = PyLong_AsLong(type.get());
        helper.checkError();
        if (tokenType != opType) continue;
        Owned spelling(PyObject_GetAttrString(token.get(), "string"));
        Owned start(PyObject_GetAttrString(token.get(), "start"));
        if (!spelling.get() || !start.get()) helper.checkError();
        const char* symbol = PyUnicode_AsUTF8(spelling.get());
        if (!symbol) helper.checkError();
        if (symbol[0] == '\0' || symbol[1] != '\0') continue;
        unsigned long line = PyLong_AsUnsignedLong(PyTuple_GetItem(start.get(), 0));
        helper.checkError();
        if (symbol[0] == '(' || symbol[0] == '[' || symbol[0] == '{') {
            if (depth++ == 0) opening = line;
        } else if (symbol[0] == ')' || symbol[0] == ']' || symbol[0] == '}') {
            // The compiler has already checked matching delimiters.
            if (depth == 0) {
                PyErr_SetString(PyExc_SyntaxError, "unbalanced continuation delimiter");
                helper.checkError();
            }
            if (--depth == 0 && line > opening) {
                info.lineTypes[opening] = START_MULTIPLE;
                for (unsigned int n = opening + 1; n <= line; ++n) info.lineTypes[n] = MULTIPLE;
            }
        }
    }
    helper.checkError();
    // Re-read on each request: Development mode can edit an existing filename.
    m_nodes[filename] = info;
    m_currentNode = info;
}
