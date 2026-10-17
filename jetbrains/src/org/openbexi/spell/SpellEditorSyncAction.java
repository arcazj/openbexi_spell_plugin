// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.intellij.openapi.actionSystem.AnActionEvent;
import com.intellij.openapi.project.DumbAwareAction;

public final class SpellEditorSyncAction extends DumbAwareAction {
    @Override public void actionPerformed(AnActionEvent event) {
        if (event.getProject() != null) SpellEditorSupport.sync(event.getProject());
    }
}
