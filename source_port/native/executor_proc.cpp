// SPDX-License-Identifier: GPL-3.0-or-later
    SPELLpython313::Owned proc(PyDict_New());
    if (!proc.get()) SPELLpythonHelper::instance().checkError();
    auto setText=[&](const std::string& key,const std::string& text) {
        SPELLpython313::Owned value(PyUnicode_FromStringAndSize(text.data(),text.size()));
        if (!value.get() || PyDict_SetItemString(proc.get(),key.c_str(),value.get())<0)
            SPELLpythonHelper::instance().checkError();
    };
    setText(DatabaseConstants::NAME,m_instanceId);
    setText(DatabaseConstants::ARGS,getConfiguration().getArguments());
    setText(DatabaseConstants::OUTPUT_DATA,m_outputDir);
    setText(DatabaseConstants::INPUT_DATA,m_inputDir);
    setText(DatabaseConstants::PARENT,getConfiguration().getParentProcId());
    if (PyDict_SetItemString(proc.get(),DatabaseConstants::STEP.c_str(),Py_None)<0 ||
        PyDict_SetItemString(proc.get(),DatabaseConstants::PREV_STEP.c_str(),Py_None)<0)
        SPELLpythonHelper::instance().checkError();
    SPELLpythonHelper::instance().install(proc.get(),DatabaseConstants::PROC);

