// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.vfs.VirtualFile;
public final class SpellDebugAction extends SpellActions {
    @Override void execute(Project project, VirtualFile file) throws Exception { SpellLaunch.debug(project, file); }
}
