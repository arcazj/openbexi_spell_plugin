// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.google.gson.JsonParser;
import com.intellij.execution.configurations.GeneralCommandLine;
import com.intellij.execution.process.CapturingProcessHandler;
import com.intellij.openapi.application.ApplicationManager;
import com.intellij.openapi.application.WriteAction;
import com.intellij.openapi.progress.ProgressIndicator;
import com.intellij.openapi.progress.Task;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.roots.AdditionalLibraryRootsListener;
import com.intellij.openapi.ui.Messages;
import com.intellij.openapi.vfs.LocalFileSystem;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Set;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

/** Editor-only definitions are generated from the same immutable image used to execute SPELL. */
public final class SpellEditorSupport {
    private static final Set<Project> RUNNING = ConcurrentHashMap.newKeySet();
    private SpellEditorSupport() {}

    public static void sync(Project project) {
        if (project.isDisposed() || !RUNNING.add(project)) return;
        var settings = SpellSettings.get(project).getState();
        String interpreter = settings.interpreter;
        String image = settings.image;
        new Task.Backgroundable(project, "Syncing SPELL editor definitions", false) {
            @Override public void run(ProgressIndicator indicator) {
                Path script = null;
                try {
                    if (project.getBasePath() == null) throw new IllegalStateException("Open a project first.");
                    if (interpreter.isBlank() || !Files.isRegularFile(Path.of(interpreter)))
                        throw new IllegalStateException("Choose an existing Python executable in SPELL Runtime Settings.");
                    Path base = Path.of(project.getBasePath()).toRealPath();
                    Path directory = base.resolve(".openbexi/editor");
                    script = Files.createTempFile("openbexi-spell-editor-", ".py");
                    try (var resource = SpellEditorSupport.class.getResourceAsStream("/editor/export_spell_editor.py")) {
                        if (resource == null) throw new IllegalStateException("This plugin is missing its editor definition exporter.");
                        Files.copy(resource, script, StandardCopyOption.REPLACE_EXISTING);
                    }
                    Path destination = directory.resolve("current");
                    indicator.setText("Reading native SPELL APIs from the configured Docker image...");
                    var command = new GeneralCommandLine(interpreter, "-I", "-B", "-X", "utf8", script.toString(),
                        "--image", image, "--output", destination.toString())
                        .withWorkDirectory(base.toFile()).withCharset(StandardCharsets.UTF_8);
                    var output = new CapturingProcessHandler(command).runProcess(180_000);
                    if (output.isTimeout()) throw new IllegalStateException("Reading SPELL definitions timed out. Check Docker and try again.");
                    if (output.getExitCode() != 0) throw new IllegalStateException(output.getStderr().isBlank() ? output.getStdout() : output.getStderr());
                    var report = JsonParser.parseString(output.getStdout().trim()).getAsJsonObject();
                    Path root = Path.of(report.get("root").getAsString()).toRealPath();
                    if (!root.equals(destination.toRealPath())) throw new IllegalStateException("Unexpected editor definition destination.");
                    var folder = LocalFileSystem.getInstance().refreshAndFindFileByIoFile(root.toFile());
                    if (folder == null) throw new IllegalStateException("IntelliJ could not find the exported definitions.");
                    folder.refresh(false, true);
                    ApplicationManager.getApplication().invokeLater(() -> {
                        try {
                            if (project.isDisposed()) return;
                            WriteAction.run(() -> AdditionalLibraryRootsListener.fireAdditionalLibraryChanged(
                                project, "SPELL editor definitions", List.of(), List.of(folder), "openbexi.spell.editor"));
                            Messages.showInfoMessage(project,
                                "SPELL editor definitions are synchronized. IntelliJ will index imports and completion.\n\n"
                                + "These .pyi files are for editing only. Use Run File with SPELL for native execution.\n"
                                + "For ordinary Python and package installation, select a valid project Python interpreter.",
                                "SPELL Editor Ready");
                        } finally { RUNNING.remove(project); }
                    });
                } catch (Exception error) {
                    RUNNING.remove(project);
                    ApplicationManager.getApplication().invokeLater(() -> {
                        if (!project.isDisposed()) Messages.showErrorDialog(project, error.getMessage(), "SPELL Editor Sync");
                    });
                } finally {
                    if (script != null) try { Files.deleteIfExists(script); } catch (java.io.IOException ignored) { }
                }
            }
        }.queue();
    }
}
