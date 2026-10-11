// SPDX-License-Identifier: GPL-3.0-or-later
// Independent host baseline: no dependency on the removed SPELL plugin.
package org.openbexi.spell.qualification;

import com.google.gson.GsonBuilder;
import com.intellij.ide.plugins.PluginManagerCore;
import com.intellij.openapi.extensions.PluginId;
import com.intellij.openapi.actionSystem.ActionManager;
import com.intellij.openapi.application.ApplicationManager;
import com.intellij.openapi.application.WriteAction;
import com.intellij.openapi.fileEditor.FileEditorManager;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.startup.StartupActivity;
import com.intellij.openapi.vfs.LocalFileSystem;
import com.intellij.openapi.wm.ToolWindowManager;
import com.intellij.execution.configurations.GeneralCommandLine;
import com.intellij.execution.executors.DefaultRunExecutor;
import com.intellij.execution.filters.TextConsoleBuilderFactory;
import com.intellij.execution.process.*;
import com.intellij.execution.ui.*;
import com.intellij.openapi.util.Key;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

public final class RemovalQualification implements StartupActivity.DumbAware {
    private static <T> T ui(Callable<T> work) throws Exception {
        FutureTask<T> task = new FutureTask<>(work);
        ApplicationManager.getApplication().invokeLater(task);
        return task.get(30, TimeUnit.SECONDS);
    }
    private static void require(boolean value, String text) { if (!value) throw new AssertionError(text); }
    @Override public void runActivity(Project project) {
        Thread.ofVirtual().start(() -> {
            Path evidence = Path.of(System.getProperty("openbexi.qualification"));
            Map<String, Object> report = new LinkedHashMap<>();
            List<String> checks = new ArrayList<>(); report.put("checks", checks); report.put("passed", false);
            StringBuffer output = new StringBuffer();
            ProcessHandler owned = null;
            try {
                require(PluginManagerCore.getPlugin(PluginId.getId("org.openbexi.spell")) == null, "SPELL plugin still installed");
                ui(() -> {
                    require(ActionManager.getInstance().getAction("OpenBEXI.Spell.Run") == null, "SPELL action remains registered");
                    require(ToolWindowManager.getInstance(project).getToolWindow("SPELL") == null, "SPELL tool window remains registered");
                    var frame = com.intellij.openapi.wm.WindowManager.getInstance().getFrame(project);
                    if (frame != null) frame.setVisible(false);
                    return null;
                });
                checks.add("Restarted same project after removal: plugin, actions and tool window absent");
                var file = ui(() -> WriteAction.compute(() -> {
                    var root = LocalFileSystem.getInstance().findFileByPath(project.getBasePath());
                    var result = root.createChildData(RemovalQualification.class, "plain_after_removal.py");
                    result.setBinaryContent("print('PYTHON_AFTER_SPELL_REMOVAL')\nassert 6 * 7 == 42\n".getBytes(StandardCharsets.UTF_8));
                    return result;
                }));
                ui(() -> { FileEditorManager.getInstance(project).openFile(file, true); return null; });
                owned = ui(() -> {
                    var handler = new OSProcessHandler(new GeneralCommandLine(System.getProperty("openbexi.interpreter"), "-I", file.getPath())
                        .withWorkDirectory(project.getBasePath()).withCharset(StandardCharsets.UTF_8));
                    handler.addProcessListener(new ProcessAdapter() {
                        @Override public void onTextAvailable(ProcessEvent event, Key type) { output.append(event.getText()); }
                    });
                    var console = TextConsoleBuilderFactory.getInstance().createBuilder(project).getConsole();
                    console.attachToProcess(handler);
                    var descriptor = new RunContentDescriptor(console, handler, console.getComponent(), "Python after SPELL removal");
                    RunContentManager.getInstance(project).showRunContent(DefaultRunExecutor.getRunExecutorInstance(), descriptor);
                    handler.startNotify(); return handler;
                });
                require(owned.waitFor(30000) && owned.getExitCode() == 0, "Ordinary Python process failed");
                require(output.toString().contains("PYTHON_AFTER_SPELL_REMOVAL"), "Ordinary Python output missing");
                checks.add("Editor opens Python and standard IDE execution console runs CPython after removal");
                report.put("passed", true);
            } catch (Throwable error) {
                var trace = new java.io.StringWriter(); error.printStackTrace(new java.io.PrintWriter(trace)); report.put("error", trace.toString());
            } finally {
                if (owned != null && !owned.isProcessTerminated()) { owned.destroyProcess(); owned.waitFor(10000); }
                try {
                    Files.writeString(evidence.resolve("console.txt"), output.toString());
                    Files.writeString(evidence.resolve("result.json"), new GsonBuilder().setPrettyPrinting().create().toJson(report));
                } catch (Exception error) { error.printStackTrace(); }
                System.exit(Boolean.TRUE.equals(report.get("passed")) ? 0 : 1);
            }
        });
    }
}
