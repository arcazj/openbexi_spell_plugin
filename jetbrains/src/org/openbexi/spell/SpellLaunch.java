// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.intellij.execution.ui.RunContentManager;
import com.intellij.execution.ExecutionException;
import com.intellij.execution.configurations.GeneralCommandLine;
import com.intellij.execution.executors.DefaultRunExecutor;
import com.intellij.execution.filters.TextConsoleBuilderFactory;
import com.intellij.execution.process.OSProcessHandler;
import com.intellij.execution.process.ProcessTerminatedListener;
import com.intellij.execution.ui.RunContentDescriptor;
import com.intellij.openapi.fileEditor.FileDocumentManager;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.vfs.VirtualFile;
import com.intellij.xdebugger.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;

public final class SpellLaunch {
    private SpellLaunch() {}
    static GeneralCommandLine command(Project project, VirtualFile file, boolean debug) throws ExecutionException {
        var settings = SpellSettings.get(project).getState();
        try {
            Path root = Path.of(project.getBasePath()).toRealPath();
            Path source = Path.of(file.getPath()).toRealPath();
            if (!source.startsWith(root)) throw new IllegalArgumentException("Procedure must be inside the project");
            if (settings.interpreter.isBlank() || !Files.isRegularFile(Path.of(settings.interpreter)))
                throw new IllegalArgumentException("Select CPython 3.13 in SPELL Runtime Settings first");
            FileDocumentManager.getInstance().saveAllDocuments();
            var command = new GeneralCommandLine(settings.interpreter, "-I", "-B", "-u", "-X", "utf8", "-m",
                debug ? "openbexi_spell_host.dap" : "openbexi_spell_host.runner", "--project", root.toString(), "--image", settings.image)
                .withWorkDirectory(root.toFile()).withCharset(StandardCharsets.UTF_8).withEnvironment("OPENBEXI_HOST_MANAGED", "1");
            if (!debug) command.addParameters("--program", source.toString(), "--", settings.arguments);
            return command;
        } catch (Exception error) { throw new ExecutionException(error.getMessage(), error); }
    }
    public static OSProcessHandler run(Project project, VirtualFile file) throws ExecutionException {
        var handler = new OSProcessHandler(command(project, file, false)) {
            @Override protected void doDestroyProcess() {
                // EOF asks the host runner to close its owned native session.
                try { getProcess().getOutputStream().close(); } catch (Exception ignored) {}
                Thread.ofVirtual().start(() -> {
                    try { if (!getProcess().waitFor(10, TimeUnit.SECONDS)) super.doDestroyProcess(); }
                    catch (InterruptedException error) { Thread.currentThread().interrupt(); super.doDestroyProcess(); }
                });
            }
        };
        handler.setShouldDestroyProcessRecursively(true);
        var console = TextConsoleBuilderFactory.getInstance().createBuilder(project).getConsole();
        console.attachToProcess(handler);
        var descriptor = new RunContentDescriptor(console, handler, console.getComponent(), "SPELL: " + file.getName());
        RunContentManager.getInstance(project).showRunContent(DefaultRunExecutor.getRunExecutorInstance(), descriptor);
        ProcessTerminatedListener.attach(handler);
        handler.startNotify();
        return handler;
    }
    public static XDebugSession debug(Project project, VirtualFile file) throws ExecutionException {
        GeneralCommandLine command = command(project, file, true);
        return XDebuggerManager.getInstance(project).newSessionBuilder(
            new XDebugProcessStarter() {
                @Override public XDebugProcess start(XDebugSession session) throws ExecutionException {
                    return new SpellDebugProcess(session, command, file);
                }
            }).sessionName("SPELL: " + file.getName()).showTab(true).startSession().getSession();
    }
}
