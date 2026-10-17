// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.intellij.openapi.actionSystem.*;
import com.intellij.openapi.project.DumbAwareAction;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.vfs.VirtualFile;
import com.intellij.openapi.ui.Messages;
import com.intellij.openapi.fileEditor.FileEditorManager;

abstract class SpellActions extends DumbAwareAction {
    @Override public ActionUpdateThread getActionUpdateThread() { return ActionUpdateThread.BGT; }
    @Override public void update(AnActionEvent event) {
        VirtualFile file = procedure(event);
        event.getPresentation().setEnabled(event.getProject() != null && file != null && !file.isDirectory() && "py".equalsIgnoreCase(file.getExtension()));
    }
    static VirtualFile procedure(AnActionEvent event) {
        VirtualFile file = event.getData(CommonDataKeys.VIRTUAL_FILE);
        if (file != null && !file.isDirectory() && "py".equalsIgnoreCase(file.getExtension())) return file;
        Project project = event.getProject();
        if (project != null) for (VirtualFile selected : FileEditorManager.getInstance(project).getSelectedFiles())
            if (!selected.isDirectory() && "py".equalsIgnoreCase(selected.getExtension())) return selected;
        return null;
    }
    @Override public final void actionPerformed(AnActionEvent event) {
        Project project = event.getProject();
        VirtualFile file = procedure(event);
        if (project == null || file == null) return;
        try { execute(project, file); }
        catch (Exception error) { Messages.showErrorDialog(project, error.getMessage(), "SPELL Runtime"); }
    }
    abstract void execute(Project project, VirtualFile file) throws Exception;
}
