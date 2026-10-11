// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;
import com.intellij.openapi.actionSystem.AnActionEvent;
import com.intellij.openapi.project.DumbAwareAction;
import com.intellij.openapi.options.ShowSettingsUtil;
public final class SpellSettingsAction extends DumbAwareAction {
    @Override public void actionPerformed(AnActionEvent event) {
        if (event.getProject() != null) ShowSettingsUtil.getInstance().showSettingsDialog(event.getProject(), SpellConfigurable.class);
    }
}
