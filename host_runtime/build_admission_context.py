"""Reproduce the installed Context/Executor graphs, then add native admission.

Uses the frozen runtime's own complete source/recipe provenance. No old binary
is edited or interposed, and both new programs require independent qualification.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import zipfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def enable_native_message_moves(text):
    """Keep message layout/copy semantics; transfer already-owned IPC values."""
    if hashlib.sha256(text.encode()).hexdigest() != (
        "c54d973818d5a1c7658d1d6669464207edb5ddd989804d898acd81c31cf2114f"
    ):
        raise ValueError("Native message move preimage differs")
    anchor = "SPELLipcMessage( const SPELLipcMessage& msg );"
    if text.count(anchor) != 1:
        raise ValueError("Native message move boundary differs")
    return text.replace(
        anchor,
        anchor + "\n    SPELLipcMessage(SPELLipcMessage&&) = default;"
        "\n    SPELLipcMessage& operator=(SPELLipcMessage&&) = default;"
        "\n    void v08FromData(const std::string& data);",
    )


def transfer_native_incoming(text):
    """Move constructor-owned parameters; preserve the independent input copy."""
    if hashlib.sha256(text.encode()).hexdigest() != (
        "45e3dcb8a2af61f575697066b443facc394ba1ee9e202a40989c67d01be5980d"
    ):
        raise ValueError("Native incoming move preimage differs")
    for old, new in (
        ("m_message(msg)", "m_message(std::move(msg))"),
        ("m_key(msg.getKey())", "m_key(m_message.getKey())"),
        (
            "SPELLipcIncomingBase(msgId,ifcName,msg,listener)",
            "SPELLipcIncomingBase(msgId,ifcName,std::move(msg),listener)",
        ),
        (
            "SPELLipcIncomingBase(requestId,ifcName,msg,listener)",
            "SPELLipcIncomingBase(requestId,ifcName,std::move(msg),listener)",
        ),
    ):
        if text.count(old) != 1:
            raise ValueError("Native incoming move boundary differs")
        text = text.replace(old, new)
    return "#include <utility>\n" + text


def replace_native_message_codec(text):
    """Remove intermediate IPC allocations without changing the class ABI."""
    if hashlib.sha256(text.encode()).hexdigest() != (
        "470c0b989e292ec61c239cbb78f343754d79c001d51c689b5f3a65adafbddc15"
    ):
        raise ValueError("Native IPC message preimage differs")
    for signature in (
        "std::string SPELLipcMessage::data() const",
        "void SPELLipcMessage::fromData( std::string data )",
    ):
        if text.count(signature) != 1:
            raise ValueError("Native IPC message boundary differs")
        start = text.index(signature)
        end = text.index("\n}", start) + 2
        text = text[:start] + text[end:]
    setter = "    m_properties[key] = value;"
    if text.count(setter) != 1:
        raise ValueError("Native IPC setter boundary differs")
    text = text.replace(setter, "    m_properties[std::move(key)] = std::move(value);")
    return (
        "#include <utility>\n"
        + text
        + '\n#include "/candidate/message_codec.H"\n'
        + '#include "/candidate/allocation_trace.H"\n'
    )


def transfer_native_output(text):
    """Keep framing/compression/error behavior; transfer the owned wire buffer."""
    if hashlib.sha256(text.encode()).hexdigest() != (
        "ead687e6c52a06552b4709fd645c7d78d781423590a2159131158e32e1b3ec02"
    ):
        raise ValueError("Native output transfer preimage differs")
    for old, new in (
        (
            "data = (doCompression ? COMPRESSION_FLAG_TRUE_STR : COMPRESSION_FLAG_FALSE_STR) + data;",
            "data.insert(0, doCompression ? COMPRESSION_FLAG_TRUE_STR : COMPRESSION_FLAG_FALSE_STR);",
        ),
        ("writeData( data );", "writeData( std::move(data) );"),
    ):
        if text.count(old) != 1:
            raise ValueError("Native output transfer boundary differs")
        text = text.replace(old, new)
    return "#include <utility>\n" + text


def replace_native_spawn(text):
    """Execute through libc spawn without running the Context's fork callbacks.

    The frozen Context is multithreaded and loads driver libraries. A child
    must not execute inherited library callbacks before replacing its image.
    Keep the original shell, command, environment, descriptors and parent PID.
    """
    start = text.index("pid_t SPELLprocess::popen(")
    end = text.index(
        "//=============================================================================",
        start,
    )
    original = text[start:end]
    if hashlib.sha256(original.encode()).hexdigest() != (
        "d6ca57f721aa356ca6928fe8f02e954c05a3ff6257c62d46f47c7d63760a9135"
    ):
        raise ValueError("Native process spawn source differs")
    replacement = """pid_t SPELLprocess::popen( std::string command )
{
    pid_t pid = -1;
    char shell[] = "bash";
    char option[] = "-c";
    char* arguments[] = {shell, option, const_cast<char*>(command.c_str()), nullptr};
    // Match the frozen port's child termination-signal unblocking, leaving
    // all other mask bits and the Context thread's own mask unchanged.
    sigset_t mask;
    int error = pthread_sigmask(SIG_BLOCK, nullptr, &mask);
    if (error == 0) {
        for (int value : {SIGINT, SIGTERM, SIGHUP, SIGQUIT}) sigdelset(&mask, value);
        posix_spawnattr_t attributes;
        error = posix_spawnattr_init(&attributes);
        if (error == 0) {
            error = posix_spawnattr_setsigmask(&attributes, &mask);
            if (error == 0) error = posix_spawnattr_setflags(&attributes, POSIX_SPAWN_SETSIGMASK);
            if (error == 0)
                error = posix_spawn(&pid, "/bin/bash", nullptr, &attributes, arguments, environ);
            posix_spawnattr_destroy(&attributes);
        }
    }
    if (error != 0) {
        // No PID or started event exists on this path. Never retry a spawn.
        THROW_EXCEPTION("Native process spawn failed", "Process creation unavailable", SPELL_ERROR_PROCESS);
    }
    return pid;
}

"""
    include = '#include "SPELL_PRC/SPELLprocessManager.H"'
    if text.count(include) != 1:
        raise ValueError("Native process include differs")
    return (text[:start] + replacement + text[end:]).replace(
        include,
        include
        + "\n#include <spawn.h>\n#include <pthread.h>\n#include <signal.h>\nextern char **environ;",
    )


def fence_external_controller_mailbox(text):
    """Close native STOP's path around executeCommand's authorization gate."""
    run = "void SPELLcontroller::run()\n{\n"
    stop = "        if (cmd.id == CMD_STOP)\n        {\n"
    if (
        text.count(run) != 1
        or text.count(stop) != 1
        or "v08_external_command_disabled(cmd.id, cmd.v08External)" in text
    ):
        raise ValueError("Ambiguous original controller STOP mailbox")
    return text.replace(
        stop,
        """        // STOP is consumed before executeCommand; fence external commands here.
        // The original stop() operation inserts a non-external safety marker.
        if (v08_external_command_disabled(cmd.id, cmd.v08External))
        {
            LOG_ERROR("V08_NATIVE_EXTERNAL_MUTATION_DENIED");
            continue;
        }
"""
        + stop,
    )


def trace_native_startup(text):
    """Fixed diagnostics at original startup boundaries; no retry or timeout change."""
    anchors = {
        "void SPELLexecutor::start()\n{\n": "entered",
        '\tLOG_INFO("Starting executor " + m_model.getInstanceId());': "admitted",
        "\tm_model.setIpcPort( m_ipc.getPort() );": "ipc-ready",
        "\t\tSPELLprocessManager::instance().startProcess( m_model.getInstanceId(), command );": "spawn-requested",
        '\t\tDEBUG("Start event received");': "process-started",
        '\t\t\tDEBUG("Executor process logged in");': "login-observed",
        "            try { v08_bind_native_executor(m_model); }": "member-bound",
        '\tDEBUG("Received executor login: " + m_model.getInstanceId() );': "login-entered",
        "\tm_executorLoggedInEvent.set();": "login-published",
    }
    if "v08_start_trace(" in text:
        raise ValueError("Native startup already instrumented")
    for anchor, phase in anchors.items():
        if text.count(anchor) != 1:
            raise ValueError("Ambiguous native startup diagnostic: " + phase)
        # The bind expression is a try/catch: inserting before its catch would
        # break C++. Observe the attempt here; success follows the whole block.
        if phase == "member-bound":
            text = text.replace(
                anchor,
                '            v08_start_trace(m_model.getInstanceId(), "binding-requested");\n'
                + '            try { v08_bind_native_executor(m_model); v08_start_trace(m_model.getInstanceId(), "member-bound"); }',
            )
        else:
            text = text.replace(
                anchor,
                anchor
                + '\n    v08_start_trace(m_model.getInstanceId(), "'
                + phase
                + '");',
            )
    return text.replace(
        '#include "/candidate/admission_gate.H"',
        '#include "/candidate/admission_gate.H"\n#include "/candidate/startup_trace.H"',
    )


def patch_native_tree(source, *, prompts=False, terminal=False):
    """Apply only to the independently reproduced frozen composition."""
    message_header = source / "include/SPELL_IPC/SPELLipcMessage.H"
    message_header.write_text(enable_native_message_moves(message_header.read_text()))
    incoming = source / "lib/SPELL_IPC/src/SPELLipcIncoming.C"
    incoming.write_text(transfer_native_incoming(incoming.read_text()))
    for relative in (
        "src/context/src/SPELLcontextMain.C",
        "src/executor/src/SPELLexecutorMain.C",
    ):
        path = source / relative
        text = path.read_text()
        entry = "int main( int argc, char** argv )\n{\n"
        if text.count(entry) != 1 or "v08_allocation_profile_start" in text:
            raise ValueError("Native profiler entry boundary differs")
        path.write_text(
            text.replace(
                entry,
                'extern "C" bool v08_allocation_profile_start() noexcept;\n'
                + entry
                + "    if (!v08_allocation_profile_start()) return 2;\n",
            )
        )
    message_codec = source / "lib/SPELL_IPC/src/SPELLipcMessage.C"
    message_codec.write_text(replace_native_message_codec(message_codec.read_text()))
    output = source / "lib/SPELL_IPC/src/SPELLipcOutput.C"
    output.write_text(transfer_native_output(output.read_text()))
    native_input = source / "lib/SPELL_IPC/src/SPELLipcInput.C"
    if (
        sha(native_input)
        != "fe0ee70bfeb33103c707365e408623aad86f89b8ced309459009cd64b90a8283"
    ):
        raise ValueError("Native resource observation preimage differs")
    input_text = native_input.read_text()
    decode = "msg.fromData( dataForMsg );"
    if input_text.count(decode) != 1:
        raise ValueError("Native input decode boundary differs")
    input_text = input_text.replace(decode, "msg.v08FromData( dataForMsg );")
    include = '#include "SPELL_IPC/SPELLipcInput.H"'
    loop = "    while(isConnected())\n    {\n"
    if input_text.count(include) != 1 or input_text.count(loop) != 1:
        raise ValueError("Native resource observation boundary differs")
    native_input.write_text(
        input_text.replace(
            include,
            include + '\n#include "/candidate/resource_trace.H"',
        ).replace(loop, loop + "        v08_resource_trace(1);\n")
    )
    # The legacy GUI client key is client-proposed/reusable. Allocate an
    # incarnation-local monotonic key instead, before addClient can replace
    # an existing channel. This applies only to the private Context GUI port.
    ipc = source / "lib/SPELL_IPC/src/SPELLipcServerInterface.C"
    ipc_text = ipc.read_text()
    marker = "\t\t\t\tif (key == 0)\n"
    if ipc_text.count(marker) != 1:
        raise ValueError("Ambiguous native GUI reconnect boundary")
    ipc_text = ipc_text.replace(
        '#include "SPELL_IPC/SPELLipcError.H"',
        '#include "SPELL_IPC/SPELLipcError.H"\n#include "/candidate/gui_policy.H"',
    )
    ipc_text = ipc_text.replace(
        marker,
        """                if (m_ifcName == "CTX-TO-GUI")
                {
                    SPELLmonitor lock(m_clientLock);
                    int last = m_usedClientKeys.empty() ? 0 : m_usedClientKeys.back();
                    try { key = v08_next_gui_key(last, key); }
                    catch (const std::exception&) {
                        delete clientSocket;
                        throw SPELLipcError("Native GUI reconnect/capacity denied");
                    }
                    m_usedClientKeys.push_back(key);
                }
                else if (key == 0)
""",
    )
    # Retain even failed/closed GUI allocations in the bounded original vector.
    # This avoids both key reuse and an ABI change in the legacy server class.
    cleanup = "            m_usedClientKeys.erase(std::remove(m_usedClientKeys.begin(),m_usedClientKeys.end(),key),m_usedClientKeys.end());"
    removal = "        if (used!=m_usedClientKeys.end()) m_usedClientKeys.erase(used);"
    if ipc_text.count(cleanup) != 1 or ipc_text.count(removal) != 1:
        raise ValueError("Ambiguous native GUI key retirement")
    ipc_text = ipc_text.replace(
        cleanup, '            if (m_ifcName != "CTX-TO-GUI")\n' + cleanup
    )
    ipc.write_text(
        ipc_text.replace(
            removal,
            '        if (m_ifcName != "CTX-TO-GUI" && used!=m_usedClientKeys.end()) m_usedClientKeys.erase(used);',
        )
    )
    message = source / "include/SPELL_IPC/SPELLipcMessage.H"
    message_text = message.read_text()
    marker = "\t\tbool hasField( std::string field ) const;"
    if message_text.count(marker) != 1:
        raise ValueError("Ambiguous native GUI field representation")
    message.write_text(
        message_text.replace(
            marker,
            marker
            + "\n        const Properties& v08Fields() const { return m_properties; }",
        )
    )
    client = source / "lib/SPELL_CTX/src/SPELLclientIPC.C"
    client_text = client.read_text()
    include = '#include "SPELL_CTX/SPELLclientIPC.H"'
    oneway = "void SPELLclientIPC::processMessage( const SPELLipcMessage& msg )\n{\n"
    request = "SPELLipcMessage SPELLclientIPC::processRequest( const SPELLipcMessage& msg )\n{\n"
    if any(client_text.count(anchor) != 1 for anchor in (include, oneway, request)):
        raise ValueError("Ambiguous native Context GUI boundary")
    client_text = client_text.replace(
        include, include + '\n#include "/candidate/gui_gate.H"'
    )
    client_text = client_text.replace(
        oneway,
        oneway
        + """    try { v08_admit_gui(msg, false); }
    catch (const std::exception&) { return; }
""",
    )
    client.write_text(
        client_text.replace(
            request,
            request
            + """    // Read only: exposes this channel's transport key, never admission.
    if (msg.getId() == "REQ_V08_GUI_KEY") {
        SPELLipcMessage response = SPELLipcHelper::createResponse("RSP_V08_GUI_KEY", msg);
        response.set("GuiKey", ISTR(msg.getKey()));
        return response;
    }
    try { v08_admit_gui(msg, true); }
    catch (const std::exception&) {
        SPELLipcMessage response = SPELLipcHelper::createErrorResponse("RSP_V08_GUI_DENIED", msg);
        response.set(MessageField::FIELD_ERROR, "V08_CONTEXT_MUTATION_DENIED");
        response.set(MessageField::FIELD_REASON, "Native Context GUI admission unavailable or rejected");
        response.set(MessageField::FIELD_FATAL, PythonConstants::False);
        return response;
    }
""",
        )
    )
    unit = source / "lib/SPELL_CTX/src/SPELLexecutor.C"
    before = sha(unit)
    if before != "e8d1c0ed2ee9b66894add739f3b0a0f880a1a2f59bc50034dde5050117fec598":
        raise ValueError("Before-spawn native preimage differs")
    text = unit.read_text()
    anchor = "void SPELLexecutor::start()\n{\n"
    if text.count(anchor) != 1:
        raise ValueError("Ambiguous native start boundary")
    # Exceptions must cross the legacy Context's original SPELLcoreException
    # handler, rather than terminate an IPC thread with std::runtime_error.
    text = text.replace(
        anchor,
        anchor
        + """    try { v08_admit_native_start(m_model, m_reconnecting); }
    catch (const std::exception&) {
        THROW_EXCEPTION("Native start denied", "Context admission unavailable or rejected", SPELL_ERROR_PROCESS);
    }
""",
    )
    include = '#include "SPELL_CTX/SPELLexecutor.H"'
    text = text.replace(include, include + '\n#include "/candidate/admission_gate.H"')
    forward_anchor = (
        "void SPELLexecutor::sendMessageToExecutor( const SPELLipcMessage& msg )\n{\n"
    )
    if text.count(forward_anchor) != 1:
        raise ValueError("Ambiguous native Executor forwarding boundary")
    text = text.replace(
        forward_anchor,
        forward_anchor
        + """    try { v08_admit_native_run(m_model, msg); }
    catch (const std::exception&) {
        LOG_ERROR("Native RUN forwarding denied by Context admission");
        return;
    }
""",
    )
    bind_anchor = "\t\t\tm_model.setPID( SPELLprocessManager::instance().getProcessId( m_model.getInstanceId() ));"
    if text.count(bind_anchor) != 1:
        raise ValueError("Ambiguous native Executor PID binding")
    text = text.replace(
        bind_anchor,
        bind_anchor
        + """
            try { v08_bind_native_executor(m_model); }
            catch (const std::exception&) {
                THROW_EXCEPTION("Native Executor denied", "Executor identity binding unavailable or rejected", SPELL_ERROR_PROCESS);
            }
""",
    )
    unit.write_text(trace_native_startup(text))
    process = source / "lib/SPELL_PRC/src/SPELLprocess.C"
    process_text = replace_native_spawn(process.read_text())
    spawned = "\t\t\tm_processPID = popen( m_command );"
    if process_text.count(spawned) != 1 or "v08_start_trace(" in process_text:
        raise ValueError("Ambiguous native process spawn diagnostic")
    process.write_text(
        process_text.replace(
            '#include "SPELL_PRC/SPELLprocessManager.H"',
            '#include "SPELL_PRC/SPELLprocessManager.H"\n#include "/candidate/startup_trace.H"',
        ).replace(
            spawned,
            '            v08_start_trace(m_identifier, "spawn-entered");\n'
            + spawned
            + '\n            v08_start_trace(m_identifier, "spawn-returned");',
        )
    )
    # Carry the immutable request through value copies in both the mailbox and
    # trace-deferred commands, then check at executeCommand before RUN effects.
    command = source / "include/SPELL_EXC/SPELLcommand.H"
    command_text = command.read_text()
    if command_text.count("    std::string earg;") != 1:
        raise ValueError("Ambiguous native command representation")
    command.write_text(
        command_text.replace(
            "    std::string earg;",
            "    std::string earg;\n    std::string v08Request;\n    bool v08External = false;",
        )
    )
    cif = source / "lib/SPELL_CIFS/src/SPELLserverCif.C"
    cif_text = cif.read_text()
    include = '#include "SPELL_IPC/SPELLipc_Executor.H"'
    message_entry = (
        "void SPELLserverCif::processMessage( const SPELLipcMessage& msg )\n{\n"
    )
    command_entry = (
        "void SPELLserverCif::processMessageCommand( const SPELLipcMessage& msg )\n{\n"
    )
    request_entry = '\tDEBUG("[CIF] Request: " + msg.getId());'
    if any(
        cif_text.count(anchor) != 1
        for anchor in (include, message_entry, command_entry, request_entry)
    ):
        raise ValueError("Ambiguous native mutation boundary")
    cif_text = cif_text.replace(
        include, include + '\n#include "/candidate/mutation_gate.H"'
    )
    cif_text = cif_text.replace(
        message_entry,
        message_entry
        + """    if (v08_message_disabled(msg.getId(), msg.hasField("ParentId") && !msg.get("ParentId").empty())) {
        v08_note_disabled_mutation(getProcId(), msg.getId());
        return;
    }
""",
    )
    cif_text = cif_text.replace(
        command_entry,
        command_entry
        + """    if (!v08_command_supported(msg.getId())) {
        v08_note_disabled_mutation(getProcId(), msg.getId());
        return;
    }
""",
    )
    cif_text = cif_text.replace(
        request_entry,
        request_entry
        + """
    if (!v08_request_supported(requestId)) {
        v08_note_disabled_mutation(getProcId(), requestId);
        response.setType(MSG_TYPE_ERROR);
        response.set(MessageField::FIELD_ERROR, "V08_NATIVE_MUTATION_DENIED");
        response.set(MessageField::FIELD_REASON, "Owner-admitted request protocol unavailable");
        response.set(MessageField::FIELD_FATAL, PythonConstants::False);
        return response;
    }
""",
    )
    marker = "    cmd.id = msgId;"
    if cif_text.count(marker) != 1:
        raise ValueError("Ambiguous native command decoding")
    cif.write_text(
        cif_text.replace(
            marker,
            marker
            + '\n    cmd.v08External = true;\n    if (msg.hasField("V08ControlRequest")) cmd.v08Request = msg.get("V08ControlRequest");',
        )
    )
    controller = source / "lib/SPELL_EXC/src/SPELLcontroller.C"
    controller_text = controller.read_text()
    controller_text = controller_text.replace(
        '#include "SPELL_EXC/SPELLcommand.H"',
        '#include "SPELL_EXC/SPELLcommand.H"\n#include "/candidate/execution_gate.H"',
    )
    execute = "void SPELLcontroller::executeCommand( const ExecutorCommand& cmd )\n{\n"
    autorun = "void SPELLcontroller::setAutoRun()\n{\n"
    if controller_text.count(execute) != 1 or controller_text.count(autorun) != 1:
        raise ValueError("Ambiguous native command consumption boundary")
    controller_text = fence_external_controller_mailbox(controller_text)
    # Record the original busy-command drop and handler return separately.
    # Neither is proof that asynchronous procedure/driver work has settled.
    drop = '\t\tLOG_WARN("Discarding command " + cmd.id);\n\t\treturn;'
    returned = (
        '\tsetCommandFinished();\n\tDEBUG("[C] Command execution finished " + cmd.id);'
    )
    if controller_text.count(drop) != 1 or controller_text.count(returned) != 1:
        raise ValueError("Ambiguous original Executor mailbox disposition points")
    controller_text = controller_text.replace(
        drop,
        '\t\tLOG_WARN("Discarding command " + cmd.id);\n'
        '\t\tv08_report_native_disposition(m_procId, cmd, "DISCARDED_PENDING");\n'
        "\t\treturn;",
    ).replace(
        returned,
        "\tsetCommandFinished();\n"
        '\tv08_report_native_disposition(m_procId, cmd, "HANDLER_RETURNED");\n'
        '\tDEBUG("[C] Command execution finished " + cmd.id);',
    )
    controller_text = controller_text.replace(
        execute,
        execute
        + """    try { v08_consume_native_run(m_procId, cmd); }
    catch (const std::exception& error) {
        std::fprintf(stderr, "V08_NATIVE_RUN_DENIED:%s\\n", error.what());
        LOG_ERROR("Native RUN consumption denied by Context admission");
        return;
    }
""",
    )
    # Hidden automatic children use the same admitted initial RUN as visible
    # children. They must reach the normal initial pause before executing code.
    controller.write_text(
        controller_text.replace(
            autorun,
            autorun
            + '    LOG_INFO("Native automatic RUN deferred to admitted command");\n    return;\n',
        )
    )
    main = source / "src/executor/src/SPELLexecutorMain.C"
    main_text = main.read_text()
    entry = "int main( int argc, char** argv )\n{\n"
    if main_text.count(entry) != 1:
        raise ValueError("Ambiguous native Executor entry point")
    # The installed Python DTA shim points at the original frozen shared graph.
    # Register this graph's init function before Python startup, so that import
    # uses the already linked candidate and cannot load a second singleton.
    main.write_text(
        main_text.replace(
            entry,
            'extern "C" PyObject* PyInit_libSPELL_DTA_v3();\n'
            + entry
            + '    if (setenv("OPENBEXI_V08_EXECUTOR_BOOTSTRAP", "1", 1) != 0) return 2;\n'
            + '    if (PyImport_AppendInittab("libSPELL_DTA_v3", PyInit_libSPELL_DTA_v3) != 0) return 2;\n',
        )
    )
    helper = source / "lib/SPELL_UTIL/src/SPELLpythonHelper.C"
    helper_text = helper.read_text()
    framework_end = """    for (const char* name: modules) {
        importAllFrom(name);
    }
}"""
    if helper_text.count(framework_end) != 1:
        raise ValueError("Ambiguous native framework bootstrap")
    # Verify the singleton during trusted bootstrap, before user tracing is
    # installed. A procedure-level generator/map-inspection assertion would
    # also exercise unrelated native debugger/frame semantics.
    helper_text = helper_text.replace(
        "#include <cstdlib>", "#include <cstdlib>\n#include <fstream>"
    )
    helper.write_text(
        helper_text.replace(
            framework_end,
            framework_end[:-1]
            + """
    // Context has its original independent metadata graph. Only the candidate
    // Executor main sets this marker, before Python initialization/user code.
    const char* bootstrap = std::getenv("OPENBEXI_V08_EXECUTOR_BOOTSTRAP");
    if (!bootstrap) return;
    if (std::string(bootstrap) != "1")
        THROW_EXCEPTION("Native singleton rejected", "Executor bootstrap marker differs", SPELL_ERROR_PYTHON_API);
    SPELLpython313::Owned module(PyImport_ImportModule("libSPELL_DTA_v3"));
    SPELLpython313::Owned spec(module.get() ? PyObject_GetAttrString(module.get(), "__spec__") : nullptr);
    SPELLpython313::Owned origin(spec.get() ? PyObject_GetAttrString(spec.get(), "origin") : nullptr);
    if (!origin.get() || !PyUnicode_Check(origin.get()) ||
        PyUnicode_CompareWithASCIIString(origin.get(), "built-in") != 0)
        THROW_EXCEPTION("Native singleton rejected", "DTA must use this Executor's built-in initializer", SPELL_ERROR_PYTHON_API);
    std::ifstream mappings("/proc/self/maps");
    if (!mappings) THROW_EXCEPTION("Native singleton rejected", "Native mappings unavailable", SPELL_ERROR_PYTHON_API);
    bool found = false;
    std::string mapping;
    while (std::getline(mappings, mapping)) {
        if (mapping.find("libspell_executor313.so") == std::string::npos) continue;
        if (mapping.find("/opt/v08-native-home/bin/libspell_executor313.so") == std::string::npos)
            THROW_EXCEPTION("Native singleton rejected", "Foreign executor library mapped", SPELL_ERROR_PYTHON_API);
        found = true;
    }
    if (!found) THROW_EXCEPTION("Native singleton rejected", "Candidate executor library missing", SPELL_ERROR_PYTHON_API);
    if (std::getenv("OPENBEXI_V08_RUNTIME_EPOCH")) {
        // Fixed trusted image source, independent of isolated Python's path.
        const int result = PyRun_SimpleString(
            "import importlib.util as _v08_util\\n"
            "_v08_spec = _v08_util.spec_from_file_location('_v08_epoch', '/candidate/epoch_connection.py')\\n"
            "_v08_epoch = _v08_util.module_from_spec(_v08_spec)\\n"
            "_v08_spec.loader.exec_module(_v08_epoch)\\n"
            "_v08_epoch.install()\\n");
        if (result != 0)
            THROW_EXCEPTION("Native epoch rejected", "Trusted driver bootstrap failed", SPELL_ERROR_PYTHON_API);
    }
}
""",
        )
    )
    service = source / "lib/SPELL_CTX/src/SPELLservice.C"
    if (
        sha(service)
        != "37e4c2b4df2ba39f7da81c21b25d10913e44ba8bac88fca1a3839e7d1e3bb2a3"
    ):
        raise ValueError("Native service-start preimage differs")
    service_anchor = "void SPELLservice::start()\n{\n"
    service_text = service.read_text()
    if service_text.count(service_anchor) != 1:
        raise ValueError("Ambiguous native service-start boundary")
    service.write_text(
        service_text.replace(
            service_anchor,
            service_anchor
            + """    THROW_EXCEPTION("Native service start denied", "Services are unqualified in the child admission profile", SPELL_ERROR_PROCESS);
""",
        )
    )
    if prompts:
        from native_prompt_patch import patch_prompt_tree

        patch_prompt_tree(source)
    if terminal:
        if not prompts:
            raise ValueError("Terminal commands require prompt settlement hooks")
        from native_terminal_patch import patch_terminal_tree

        patch_terminal_tree(source)
    return before


def native_graph(source, libraries, program):
    folder = "executorcmd" if program == "ExecutorCmd_v3" else program.lower()
    makefile = source / ("src/" + folder + "/Makefile.am")
    logical = makefile.read_text().replace("\\\n", " ")
    name = "SPELL_" + program
    dependencies = re.findall(r"^" + name + r"_LDADD\s*=\s*([^\n]+)", logical, re.M)
    mains = re.findall(r"^" + name + r"_SOURCES\s*=\s*([^\n]+)", logical, re.M)
    if len(dependencies) != 1 or len(mains) != 1:
        raise ValueError("Ambiguous original native manifest")
    names = re.findall(r"/lib/(SPELL_\w+)/lib\1_v[23]\.la", dependencies[0])
    library = libraries(source)
    units = [source / p for name in names for p in library[name]["units"]]
    units += [makefile.parent / name for name in mains[0].split()]
    if not units or len(units) != len(set(units)):
        raise ValueError("Invalid native source graph")
    return units


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--native-prompts",
        action="store_true",
        help="Build private owner-bound prompt hooks; needs matching agent",
    )
    parser.add_argument("--native-terminal", action="store_true")
    args = parser.parse_args()
    if args.native_terminal:
        args.native_prompts = True
    import spell_native

    runtime = Path(spell_native.__file__).parent
    recipe = runtime / "provenance/source_port"
    sys.path.insert(0, str(recipe))
    from native_patches import apply_tree
    from integrated_patches import apply_native_tree
    from native_manifest import libraries

    archive = runtime / "provenance/SPELL2.6.10-src.zip"
    manifest = json.loads((runtime / "manifest.json").read_text())
    if sha(archive) != manifest["archive_sha256"]:
        raise ValueError("Native source archive differs")
    source = Path("/tmp/v08-context-source")
    source.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            path = (source / member.filename).resolve()
            if not path.is_relative_to(source):
                raise ValueError("Source archive traversal")
            if not member.is_dir():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(bundle.read(member))
    apply_tree(source)
    composition = apply_native_tree(
        source, archive, Path("/tmp/v08-context-composition")
    )
    expected = dict(manifest["composition"]["native"])
    expected.pop("manifest_sha256")
    if composition != expected:
        raise ValueError("Installed native source composition does not reproduce")
    before = patch_native_tree(
        source, prompts=args.native_prompts, terminal=args.native_terminal
    )
    build = Path("/tmp/v08-context-objects")
    build.mkdir()
    flags = [
        "c++",
        "-std=c++17",
        "-fPIC",
        "-g",
        "-O1",
        "-pthread",
        "-fmax-errors=4",
        "-fsanitize=address,undefined",
        "-fno-sanitize-recover=all",
        "-fno-omit-frame-pointer",
        "-I" + str(source / "include"),
        "-I" + sysconfig.get_path("include"),
    ]
    if args.native_terminal:
        flags.append("-DOPENBEXI_V08_TERMINAL=1")
    graphs = {
        name: native_graph(source, libraries, name) for name in ("Context", "Executor")
    }
    # Reproduce the frozen common runtime's 13-library graph, not only the
    # server executable's dependency subset. These two port support sources are
    # explicit supplemental units in the frozen native_build/executor_build.
    runtime_graph = native_graph(source, libraries, "ExecutorCmd_v3")[:-1]
    support = [
        recipe / "native" / name for name in ("ws_filter.cpp", "continuation.cpp")
    ]
    for path in support:
        if sha(path) != manifest["inputs"][path.relative_to(recipe).as_posix()]:
            raise ValueError("Frozen native support source differs")
    flags.append("-I" + str(recipe / "native"))
    units = sorted(
        set(
            [path for graph in graphs.values() for path in graph]
            + runtime_graph
            + support
        )
    )

    def compile_unit(path):
        name = (
            path.relative_to(source).as_posix()
            if path.is_relative_to(source)
            else "support/" + path.name
        )
        obj = build / (name.replace("/", "_") + ".o")
        result = subprocess.run(
            flags + ["-c", str(path), "-o", str(obj)], capture_output=True, timeout=180
        )
        obj.with_suffix(".log").write_bytes(result.stdout + result.stderr)
        if result.returncode:
            print((result.stdout + result.stderr).decode(), file=sys.stderr)
            raise RuntimeError("Native compilation failed: " + name)
        return dict(unit=name, sha256=sha(path), object=str(obj))

    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(compile_unit, units))
    home = Path("/opt/v08-native-home")
    home.mkdir()
    for child in runtime.iterdir():
        if child.name != "bin":
            (home / child.name).symlink_to(child, target_is_directory=child.is_dir())
    binaries = home / "bin"
    binaries.mkdir()
    for child in (runtime / "bin").iterdir():
        if child.name not in {
            "SPELL-Context",
            "SPELL-Executor",
            "SPELL-Executor_v3",
            "libspell_executor313.so",
        }:
            (binaries / child.name).symlink_to(child)
    indexed = {row["unit"]: row["object"] for row in records}
    shared = binaries / "libspell_executor313.so"
    shared_objects = [
        indexed[path.relative_to(source).as_posix()] for path in runtime_graph
    ]
    shared_objects += [indexed["support/" + path.name] for path in support]
    subprocess.run(
        [
            "c++",
            "-shared",
            "-pthread",
            "-fsanitize=address,undefined",
            "-Wl,--no-undefined",
            *shared_objects,
            "-L" + sysconfig.get_config_var("LIBDIR"),
            "-lpython3.13",
            "-llog4cplus",
            "-lxerces-c",
            "-lz",
            "-lmenu",
            "-lncurses",
            "-o",
            str(shared),
        ],
        check=True,
        timeout=120,
    )
    programs = {}
    for name, graph in graphs.items():
        program = binaries / ("SPELL-" + name)
        objects = [indexed[path.relative_to(source).as_posix()] for path in graph]
        if name == "Executor":
            objects = [
                indexed[graph[-1].relative_to(source).as_posix()],
                "-L" + str(binaries),
                "-lspell_executor313",
                "-Wl,-rpath,$ORIGIN",
            ]
        subprocess.run(
            [
                "c++",
                "-pthread",
                "-fsanitize=address,undefined",
                "-Wl,--no-undefined",
                *objects,
                "-L" + sysconfig.get_config_var("LIBDIR"),
                "-lpython3.13",
                "-llog4cplus",
                "-lxerces-c",
                "-lz",
                "-lmenu",
                "-lncurses",
                "-o",
                str(program),
            ],
            check=True,
            timeout=120,
        )
        programs[name] = sha(program)
    (binaries / "SPELL-Executor_v3").symlink_to("SPELL-Executor")
    # The opt-in session must use the same candidate IPC codec as its native
    # peers. The frozen host bridge and default session remain separate.
    bridge_source = Path("/candidate/private_bridge.cpp")
    fields = set()
    for header in (source / "include/SPELL_IPC").glob("*.H"):
        fields.update(
            re.findall(r'FIELD_\w+\s*\(\s*"([^"]+)"\s*\)', header.read_text())
        )
    if not {"Csp", "ExecutorStatus", "VarName", "VarValue", "ContextPort"} <= fields:
        raise ValueError("Native bridge field inventory differs")
    fields.update({"DefaultProvided", "TimeoutMicroseconds"})
    fields_path = Path("/candidate/fields.inc")
    fields_path.write_text(
        "static const char* fieldNames[] = {\n"
        + ",\n".join(json.dumps(field) for field in sorted(fields))
        + "\n};\n"
    )
    bridge_binary = binaries / "spell-host-ipc"
    subprocess.run(
        flags
        + [
            str(bridge_source),
            "-L" + str(binaries),
            "-lspell_executor313",
            "-Wl,-rpath,$ORIGIN",
            "-L" + sysconfig.get_config_var("LIBDIR"),
            "-lpython3.13",
            "-o",
            str(bridge_binary),
        ],
        check=True,
        timeout=120,
    )
    # Symbolize private executable offsets offline without changing dynamic
    # symbol interposition. Shared-library symbols are already discoverable.
    context_symbols = []
    for line in subprocess.check_output(
        ["nm", "-n", "-S", "--defined-only", str(binaries / "SPELL-Context")],
        text=True,
    ).splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[2] in {"T", "t", "W", "w"}:
            context_symbols.append([int(fields[0], 16), int(fields[1], 16), fields[3]])
    if len(context_symbols) > 20000:
        raise ValueError("Native diagnostic symbol inventory exceeds bound")
    report = dict(
        schema=1,
        native_start_qualified=False,
        native_prompt_hooks=args.native_prompts,
        native_terminal_hooks=args.native_terminal,
        full_v08_qualified=False,
        original_context_sha256=sha(runtime / "bin/SPELL-Context"),
        archive_sha256=sha(archive),
        original_unit_sha256=before,
        gate_sha256=sha(Path("/candidate/admission_gate.H")),
        candidate_context_sha256=programs["Context"],
        context_function_symbols=context_symbols,
        candidate_executor_sha256=programs["Executor"],
        original_executor_sha256=sha(runtime / "bin/SPELL-Executor_v3"),
        candidate_shared_runtime_sha256=sha(shared),
        candidate_bridge_sha256=sha(bridge_binary),
        candidate_bridge_source_sha256=sha(bridge_source),
        candidate_bridge_fields_sha256=sha(fields_path),
        epoch_bootstrap_sha256=sha(Path("/candidate/epoch_connection.py")),
        original_shared_runtime_sha256=sha(runtime / "bin/libspell_executor313.so"),
        shared_runtime_library_units=len(runtime_graph),
        supplemental_units={path.name: sha(path) for path in support},
        graph_units={name: len(graph) for name, graph in graphs.items()},
        admission_headers={
            path.name: sha(path) for path in Path("/candidate").glob("*.H")
        },
        units=records,
        compiler=subprocess.check_output(["c++", "--version"], text=True).splitlines()[
            0
        ],
    )
    (home / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    shutil.rmtree(source)


if __name__ == "__main__":
    main()
