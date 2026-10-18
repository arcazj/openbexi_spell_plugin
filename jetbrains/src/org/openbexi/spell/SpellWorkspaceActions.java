// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;
import com.intellij.openapi.actionSystem.*;
import com.intellij.openapi.project.DumbAwareAction;
import com.intellij.icons.AllIcons;

public final class SpellWorkspaceActions {
    private SpellWorkspaceActions() { }
    public static final class Open extends DumbAwareAction {
        @Override public void update(AnActionEvent event) { event.getPresentation().setEnabled(event.getProject() != null); }
        @Override public void actionPerformed(AnActionEvent event) { if (event.getProject() != null) SpellWorkspace.get(event.getProject()).show(); }
    }
    public abstract static class Control extends DumbAwareAction {
        private final String command;
        protected Control(String text, String command, javax.swing.Icon icon) { super(text, text + " the selected SPELL procedure", icon); this.command = command; }
        @Override public ActionUpdateThread getActionUpdateThread() { return ActionUpdateThread.EDT; }
        @Override public void update(AnActionEvent event) {
            var session = event.getProject() == null ? null : SpellWorkspace.get(event.getProject()).selected();
            boolean active = session != null && session.active() && session.controlling && session.connection.equals("Connected") && session.pending.isBlank();
            boolean paused = active && ("Paused".equalsIgnoreCase(session.status) || "Interrupted".equalsIgnoreCase(session.status));
            boolean running = active && java.util.Set.of("RUNNING", "WAITING", "PROMPT").contains(session.status.toUpperCase(java.util.Locale.ROOT));
            event.getPresentation().setEnabled(active && (command.equals("stop") || command.equals("pause") && running || !command.equals("pause") && paused));
        }
        @Override public void actionPerformed(AnActionEvent event) {
            if (event.getProject() == null) return; var workspace = SpellWorkspace.get(event.getProject());
            if (command.equals("stop")) workspace.stop(workspace.selected()); else workspace.control(command);
        }
    }
    public static final class Stop extends Control { public Stop() { super("Abort", "stop", AllIcons.Actions.Suspend); } }
    public static final class Pause extends Control { public Pause() { super("Pause", "pause", AllIcons.Actions.Pause); } }
    public static final class Continue extends Control { public Continue() { super("Continue", "continue", AllIcons.Actions.Resume); } }
    public static final class Step extends Control { public Step() { super("Step over", "next", AllIcons.Actions.TraceOver); } }
}
