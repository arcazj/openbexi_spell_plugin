// SPDX-License-Identifier: GPL-3.0-or-later
// Separate test plugin: this class is never shipped in the runtime ZIP.
package org.openbexi.spell.qualification;

import com.google.gson.GsonBuilder;
import com.intellij.openapi.application.ApplicationManager;
import com.intellij.openapi.application.WriteAction;
import com.intellij.openapi.fileEditor.FileEditorManager;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.startup.StartupActivity;
import com.intellij.openapi.vfs.LocalFileSystem;
import com.intellij.openapi.vfs.VirtualFile;
import com.intellij.openapi.wm.WindowManager;
import com.intellij.openapi.wm.ToolWindowManager;
import com.intellij.xdebugger.*;
import com.intellij.xdebugger.breakpoints.*;
import com.intellij.xdebugger.frame.*;
import com.intellij.xdebugger.evaluation.EvaluationMode;
import com.intellij.execution.process.*;
import com.intellij.openapi.util.Key;
import org.openbexi.spell.*;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.BooleanSupplier;

public final class HostQualification implements StartupActivity.DumbAware {
    private static final AtomicBoolean started = new AtomicBoolean();
    @Override public void runActivity(Project project) {
        if (System.getProperty("openbexi.qualification") == null || !started.compareAndSet(false, true)) return;
        Thread.ofVirtual().name("openbexi-host-qualification").start(() -> qualify(project));
    }
    private static <T> T ui(Callable<T> work) throws Exception {
        FutureTask<T> result = new FutureTask<>(work);
        ApplicationManager.getApplication().invokeLater(result);
        return result.get(30, TimeUnit.SECONDS);
    }
    private static void waitFor(BooleanSupplier condition, String message) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(45);
        while (!condition.getAsBoolean() && System.nanoTime() < deadline) Thread.sleep(25);
        require(condition.getAsBoolean(), message);
    }
    private static void require(boolean value, String message) { if (!value) throw new AssertionError(message); }
    private static VirtualFile source(Project project, String name, String text) throws Exception {
        VirtualFile file = ui(() -> WriteAction.compute(() -> {
            VirtualFile root = LocalFileSystem.getInstance().findFileByPath(project.getBasePath());
            require(root != null, "Project root not visible to IDE");
            VirtualFile created = root.createChildData(HostQualification.class, name);
            created.setBinaryContent(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            return created;
        }));
        ui(() -> { FileEditorManager.getInstance(project).openFile(file, true); return null; });
        return file;
    }
    private static ProcessAdapter collect(StringBuffer output) {
        return new ProcessAdapter() {
            @Override public void onTextAvailable(ProcessEvent event, Key type) { output.append(event.getText()); }
        };
    }
    private static XValue variable(XDebugSession session, String name) throws Exception {
        CompletableFuture<XValue> result = new CompletableFuture<>();
        ui(() -> {
            session.getCurrentStackFrame().computeChildren(new XCompositeNode() {
                @Override public boolean isObsolete() { return false; }
                @Override public void addChildren(XValueChildrenList children, boolean last) {
                    for (int i = 0; i < children.size(); i++)
                        if (children.getName(i).equals(name)) result.complete(children.getValue(i));
                    if (last && !result.isDone()) result.completeExceptionally(new AssertionError("Variable missing: " + name));
                }
                @Override public void tooManyChildren(int count) { result.completeExceptionally(new AssertionError("Truncated variables")); }
                @Override public void setAlreadySorted(boolean sorted) { }
                @Override public void setErrorMessage(String text) { result.completeExceptionally(new AssertionError(text)); }
                @Override public void setErrorMessage(String text, XDebuggerTreeNodeHyperlink link) { setErrorMessage(text); }
                @Override public void setMessage(String text, javax.swing.Icon icon, com.intellij.ui.SimpleTextAttributes attrs, XDebuggerTreeNodeHyperlink link) { }
            });
            return null;
        });
        return result.get(15, TimeUnit.SECONDS);
    }
    private void qualify(Project project) {
        Path evidence = Path.of(System.getProperty("openbexi.qualification"));
        Map<String, Object> report = new LinkedHashMap<>();
        List<String> checks = new ArrayList<>(); report.put("checks", checks); report.put("passed", false);
        StringBuffer output = new StringBuffer();
        List<ProcessHandler> owned = new ArrayList<>();
        XDebugSession debug = null;
        try {
            Files.writeString(evidence.resolve("startup.txt"), project.getBasePath());
            ui(() -> {
                var settings = SpellSettings.get(project).getState();
                settings.interpreter = System.getProperty("openbexi.interpreter");
                var tool = ToolWindowManager.getInstance(project).getToolWindow("SPELL");
                require(tool != null, "SPELL tool window was not registered"); tool.show();
                // Keep this private qualification instance out of the user's way.
                var frame = WindowManager.getInstance().getFrame(project);
                if (frame != null) frame.setVisible(false);
                return null;
            });
            checks.add("Installed plugin settings and tool window in actual IDE");
            VirtualFile run = source(project, "run.py", "from spell.lang.functions import Display\nfrom pathlib import Path\nDisplay('JETBRAINS_NATIVE_RUN')\nPath('answer.txt').write_text('42')\n");
            OSProcessHandler handler = ui(() -> { var process = SpellLaunch.run(project, run); process.addProcessListener(collect(output)); return process; });
            owned.add(handler);
            waitFor(handler::isProcessTerminated, "Run did not finish");
            require(handler.getExitCode() == 0 && output.toString().contains("JETBRAINS_NATIVE_RUN"), "Native Run failed: " + output);
            checks.add("Native Run through IDE process handler and console");
            VirtualFile control = source(project, "control.py", "from spell.lang.functions import Display\nvalue = 21\nanswer = value + 2\nDisplay('JETBRAINS_DEBUG_' + str(answer))\nassert answer == 42\n");
            XLineBreakpoint<?> breakpoint = ui(() -> WriteAction.compute(() ->
                XDebuggerManager.getInstance(project).getBreakpointManager().addLineBreakpoint(
                    XBreakpointType.EXTENSION_POINT_NAME.findExtension(SpellBreakpointType.class), control.getUrl(), 2, new SpellBreakpointType.Properties())));
            debug = ui(() -> SpellLaunch.debug(project, control));
            XDebugSession session = debug;
            owned.add(session.getDebugProcess().getProcessHandler());
            session.getDebugProcess().getProcessHandler().addProcessListener(collect(output));
            CountDownLatch paused = new CountDownLatch(1), stopped = new CountDownLatch(1);
            ui(() -> { session.addSessionListener(new XDebugSessionListener() {
                @Override public void sessionPaused() { paused.countDown(); }
                @Override public void sessionStopped() { stopped.countDown(); }
            }); return null; });
            require(paused.await(45, TimeUnit.SECONDS), "Debugger never paused");
            require(ui(() -> session.getCurrentPosition().getLine()) == 2, "Wrong native source position");
            XValue value = variable(session, "value");
            require("21".equals(value.getModifier().getInitialValueEditorText()), "Wrong initial native variable");
            CompletableFuture<Void> edited = new CompletableFuture<>();
            ui(() -> {
                value.getModifier().setValue(XDebuggerUtil.getInstance().createExpression("40", null, null, EvaluationMode.EXPRESSION), new XValueModifier.XModificationCallback() {
                    @Override public void valueModified() { edited.complete(null); }
                    @Override public void errorOccurred(String message) { edited.completeExceptionally(new AssertionError(message)); }
                }); return null;
            });
            edited.get(15, TimeUnit.SECONDS);
            require("40".equals(variable(session, "value").getModifier().getInitialValueEditorText()), "Native variable edit did not persist");
            ui(() -> {
                var frame = WindowManager.getInstance().getFrame(project);
                if (frame != null) {
                    var content = frame.getRootPane();
                    var capture = new BufferedImage(Math.max(1, content.getWidth()), Math.max(1, content.getHeight()), BufferedImage.TYPE_INT_RGB);
                    var graphics = capture.createGraphics(); content.printAll(graphics); graphics.dispose();
                    ImageIO.write(capture, "png", evidence.resolve("debugger.png").toFile());
                }
                return null;
            });
            CountDownLatch stepped = new CountDownLatch(1);
            ui(() -> { session.addSessionListener(new XDebugSessionListener() {
                @Override public void sessionPaused() { stepped.countDown(); }
            }); session.stepInto(); return null; });
            require(stepped.await(30, TimeUnit.SECONDS), "Step never paused");
            require(ui(() -> session.getCurrentPosition().getLine()) == 3, "Wrong Step position");
            ui(() -> { WriteAction.run(() -> XDebuggerManager.getInstance(project).getBreakpointManager().removeBreakpoint(breakpoint)); session.resume(); return null; });
            require(stopped.await(45, TimeUnit.SECONDS), "Debug session did not stop");
            waitFor(() -> session.getDebugProcess().getProcessHandler().isProcessTerminated(), "Debug adapter was not reaped");
            require(output.toString().contains("JETBRAINS_DEBUG_42"), "Final debugger output missing: " + output);
            checks.add("XDebugger breakpoint, stack/source position, variable edit, Step, Continue and output");
            VirtualFile prompt = source(project, "prompt.py", "from spell.lang.functions import Prompt, Display\nfrom spell.lang.constants import YES_NO\nfrom spell.lang.modifiers import Type\nassert Prompt('JETBRAINS_PROMPT?', {Type:YES_NO}) is True\nDisplay('JETBRAINS_PROMPT_COMPLETE')\n");
            debug = ui(() -> SpellLaunch.debug(project, prompt));
            XDebugSession prompting = debug;
            ProcessHandler promptHandler = prompting.getDebugProcess().getProcessHandler();
            owned.add(promptHandler); promptHandler.addProcessListener(collect(output));
            waitFor(() -> output.toString().contains("Enter the native option index:"), "Native prompt did not reach IDE console");
            promptHandler.getProcessInput().write("0\n".getBytes(java.nio.charset.StandardCharsets.UTF_8));
            promptHandler.getProcessInput().flush();
            waitFor(promptHandler::isProcessTerminated, "Prompt session did not stop");
            require(output.toString().contains("JETBRAINS_PROMPT_COMPLETE"), "Prompt answer failed");
            checks.add("Native prompt and answer through IDE console input");
            VirtualFile loop = source(project, "stop.py", "import time\nfrom spell.lang.functions import Display\nDisplay('JETBRAINS_STOP_READY')\nwhile True:\n    time.sleep(0.02)\n");
            OSProcessHandler looping = ui(() -> { var process = SpellLaunch.run(project, loop); process.addProcessListener(collect(output)); return process; });
            owned.add(looping);
            waitFor(() -> output.toString().contains("JETBRAINS_STOP_READY"), "Loop did not start");
            ui(() -> { looping.destroyProcess(); return null; });
            waitFor(looping::isProcessTerminated, "IDE Stop did not reap the native runner");
            checks.add("IDE Stop gracefully closes its owned native run");
            report.put("passed", true);
        } catch (Throwable error) {
            var trace = new java.io.StringWriter(); error.printStackTrace(new java.io.PrintWriter(trace)); report.put("error", trace.toString());
        } finally {
            if (debug != null) {
                XDebugSession session = debug;
                try { ui(() -> { session.stop(); return null; }); } catch (Exception ignored) {}
            }
            for (ProcessHandler process : owned) {
                if (!process.isProcessTerminated()) process.destroyProcess();
                process.waitFor(15000);
            }
            try {
                Files.writeString(evidence.resolve("console.txt"), output.toString());
                Files.writeString(evidence.resolve("result.json"), new GsonBuilder().setPrettyPrinting().create().toJson(report));
            } catch (Exception error) { error.printStackTrace(); }
            System.exit(Boolean.TRUE.equals(report.get("passed")) ? 0 : 1);
        }
    }
}
