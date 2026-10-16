"""Expose the already evaluated calling arguments as the LRM p81 PROC dictionary.

SPDX-License-Identifier: GPL-3.0-or-later
Keep the original class ABI and central CPython port unchanged. This recipe is
prepared independently; native baseline and installed qualification are required.
"""
import hashlib

PREIMAGES = {
    'lib/SPELL_EXC/src/SPELLexecutorImpl.C': (
        '3a891afdf5e0dbcd75f97db263e3c30311c597872e434fc91b6c993683b2b0df',
        '6bcf61d299669fc28b713592acaea65a02ba21b33d751db47416ab88f5f0e450'),
    'lib/SPELL_EXC/src/SPELLserviceImpl.C': (
        '9e56ddfa666429777f37ab7bedb76de9a539145050123096554339bb1ea40382',
        '13153f3cc00a747a2eab5524eac12f47401d4f1ccf56a24f3de66ef28397728f'),
}


def apply(name, original, ported):
    if tuple(hashlib.sha256(value).hexdigest() for value in (original, ported)) != PREIMAGES.get(name):
        raise ValueError('Procedure dictionary preimage differs: '+name)
    text=ported.decode('utf-8')

    def replace(before, after):
        nonlocal text
        if text.count(before)!=1:
            raise ValueError('Procedure dictionary anchor differs: '+before)
        text=text.replace(before, after)

    replace('''\t        \tm_frameManager->reset();
\t        \tcontinueExecuting = true;''','''\t        \tm_frameManager->reset();
                // RELOAD starts a new procedure database, unlike RECOVER.
                // Preserve the evaluated initial arguments in interpreter state.
                loadExecutionEnvironment();
\t        \tcontinueExecuting = true;''')
    replace('''\t\t\t\t\t// We will recover, so do not reset entities
\t\t\t\t\tresetEntities = false;''','''                    // Error handling can return after either RELOAD or RECOVER.
                    // Only recovery retains the old call stack and initial step.
                    resetEntities = m_controller->shouldReload();
                    m_initStepDone = !resetEntities;''')

    replace('    helper.install(args.get(),"ARGS");', '''    helper.install(args.get(),"ARGS");
    // Preserve the values evaluated above without evaluating caller code twice.
    // Interpreter ownership avoids process-static references surviving finalization
    // and does not change the executor/service layout or procedure globals.
    PyObject* state = PyInterpreterState_GetDict(PyInterpreterState_Get());
    if (!state) { PyErr_NoMemory(); helper.checkError(); }
    Owned initialArguments(PyDict_Copy(values.get()));
    if (!initialArguments.get() || PyDict_SetItemString(state,
            "openbexi.spell.proc.arguments", initialArguments.get())<0)
        helper.checkError();''')
    replace('    setText(DatabaseConstants::ARGS,getConfiguration().getArguments());', '''    PyObject* state = PyInterpreterState_GetDict(PyInterpreterState_Get());
    if (!state) { PyErr_NoMemory(); SPELLpythonHelper::instance().checkError(); }
    PyObject* initialArguments = PyDict_GetItemString(state,"openbexi.spell.proc.arguments");
    if (!initialArguments || !PyDict_Check(initialArguments)) {
        PyErr_SetString(PyExc_RuntimeError,"Calling arguments were not initialized");
        SPELLpythonHelper::instance().checkError();
    }
    SPELLpython313::Owned arguments(PyDict_Copy(initialArguments));
    if (!arguments.get() || PyDict_SetItemString(proc.get(),
            DatabaseConstants::ARGS.c_str(),arguments.get())<0)
        SPELLpythonHelper::instance().checkError();''')
    return text.encode('utf-8')
