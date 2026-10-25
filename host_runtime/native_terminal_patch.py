"""Private ABORT/CLOSE overlay applied after the exact prompt composition."""
# SPDX-License-Identifier: GPL-3.0-or-later


def patch_terminal_tree(source):
    header = source / "include/SPELL_CIFS/SPELLserverCif.H"
    head = header.read_text()
    declaration = "bool cancelPrompt(const SPELLipcMessage* ownerReply = nullptr);"
    if head.count(declaration) != 1:
        raise ValueError("Native terminal prompt declaration differs")
    head = head.replace(
        declaration,
        'bool cancelPrompt(const SPELLipcMessage* ownerReply = nullptr, const std::string& terminalRequest = "");',
    )
    unit = source / "lib/SPELL_CIFS/src/SPELLserverCif.C"
    text = unit.read_text()

    def replace(before, after):
        nonlocal text
        if text.count(before) != 1:
            raise ValueError("Native terminal composition differs: " + before[:64])
        text = text.replace(before, after)

    replace(
        '#include "/candidate/prompt_gate.H"',
        '#include "/candidate/prompt_gate.H"\n#include "/candidate/execution_gate.H"',
    )
    entry = "void SPELLserverCif::processMessage( const SPELLipcMessage& msg )\n{\n"
    replace(
        entry,
        entry
        + """    if (v08_terminal_command(msg.getId())) {
        // Before prompt cancellation, CLOSE state changes, or mailbox insertion.
        if (!v08_terminal_valid(msg.getId(), msg.getType() == MSG_TYPE_ONEWAY,
                                msg.v08Fields(), getProcId())) {
            v08_note_disabled_mutation(getProcId(), msg.getId());
            return;
        }
        ExecutorCommand cmd;
        cmd.id = msg.getId();
        cmd.v08External = true;
        cmd.v08Request = msg.get("V08ControlRequest");
        try {
            v08_admit_terminal(getProcId(), cmd.v08Request, cmd.id);
            if (cmd.id == "CMD_ABORT" && cancelPrompt(nullptr, cmd.v08Request)) {
                v08_take_terminal(getProcId(), cmd.v08Request, cmd.id);
                v08_report_native_disposition(getProcId(), cmd, "HANDLER_RETURNED");
                return;
            }
            if (cmd.id == "CMD_CLOSE") {
                cancelPrompt(nullptr, cmd.v08Request);
                // The Python prompt waiter must persist its actual outcome
                // before CLOSE prevents further IPC and finalizes the executor.
                std::unique_lock<std::mutex> answer(m_promptAnswerLock);
                if (!m_promptAnswerReady.wait_for(answer, std::chrono::seconds(5),
                        [this]() { return m_v08PromptId.empty() || m_v08PromptUncertain; })
                    || m_v08PromptUncertain)
                    throw std::runtime_error("Terminal prompt settlement uncertain");
                answer.unlock();
                { SPELLmonitor guard(m_ipcLock); setClosing(); }
            }
            SPELLexecutor::instance().command(cmd, true);
        } catch (const std::exception&) {
            // The consumed grant remains spent; never retry an unknown effect.
            v08_note_disabled_mutation(getProcId(), msg.getId());
        }
        return;
    }
""",
    )
    replace(
        "bool SPELLserverCif::cancelPrompt(const SPELLipcMessage* ownerReply)",
        "bool SPELLserverCif::cancelPrompt(const SPELLipcMessage* ownerReply, const std::string& terminalRequest)",
    )
    replace(
        'm_v08PromptOutcome = ownerReply ? "CANCEL_SELECTED" : "UNKNOWN";',
        'm_v08PromptOutcome = ownerReply ? "CANCEL_SELECTED" : (!terminalRequest.empty() ? "TERMINAL_CANCELLED" : "UNKNOWN");',
    )
    replace(
        "        m_v08PromptId.clear();",
        "        m_v08PromptId.clear();\n        m_promptAnswerReady.notify_all();",
    )
    # The generic command entry is defense in depth against alternate call paths.
    replace(
        "    if (!v08_command_supported(msg.getId())) {",
        "    if (!v08_command_supported(msg.getId()) || v08_terminal_command(msg.getId())) {",
    )
    controller = source / "lib/SPELL_EXC/src/SPELLcontroller.C"
    controller_text = controller.read_text()
    close_entry = (
        "void SPELLcontroller::doClose()\n{\n"
        '    DEBUG("[C] Do close");\n    m_finished = true;\n'
    )
    if controller_text.count(close_entry) != 1:
        raise ValueError("Native terminal close handler differs")
    controller_text = controller_text.replace(
        close_entry,
        close_entry
        + """    // Like ABORT/FINISH, CLOSE must release a scheduler wait (including
    // blocking StartProc) before finalization. doContinue only releases the
    // controller stepping gate and cannot wake the scheduler's language lock.
    SPELLexecutor::instance().getScheduler().abortWait( false );
""",
    )
    header.write_text(head)
    unit.write_text(text)
    controller.write_text(controller_text)
