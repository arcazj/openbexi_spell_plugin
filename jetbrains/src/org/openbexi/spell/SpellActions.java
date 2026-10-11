// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.intellij.openapi.actionSystem.*;
import com.intellij.openapi.project.DumbAwareAction;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.vfs.VirtualFile;
import com.intellij.openapi.ui.Messages;

abstract class SpellActions extends DumbAwareAction {
    @Override public ActionUpdateThread getActionUpdateThread() { return ActionUpdateThread.BGT; }
    @Override public void update(AnActionEvent event) {
        VirtualFile file = event.getData(CommonDataKeys.VIRTUAL_FILE);
        event.getPresentation().setEnabled(event.getProject() != null && file != null && !file.isDirectory() && "py".equalsIgnoreCase(file.getExtension()));
    }
    @Override public final void actionPerformed(AnActionEvent event) {
        Project project = event.getProject();
        VirtualFile file = event.getData(CommonDataKeys.VIRTUAL_FILE);
        if (project == null || file == null) return;
        try { execute(project, file); }
        catch (Exception error) { Messages.showErrorDialog(project, error.getMessage(), "SPELL Runtime"); }
    }
    abstract void execute(Project project, VirtualFile file) throws Exception;
}
