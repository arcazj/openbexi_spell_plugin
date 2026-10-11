// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;
import com.intellij.openapi.actionSystem.*;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.wm.ToolWindow;
import com.intellij.openapi.wm.ToolWindowFactory;
import com.intellij.ui.content.ContentFactory;
import java.awt.BorderLayout;
import javax.swing.*;

public final class SpellToolWindow implements ToolWindowFactory {
    @Override public void createToolWindowContent(Project project, ToolWindow window) {
        JPanel panel = new JPanel(new BorderLayout(8, 8));
        JTextArea help = new JTextArea("SPELL Development\n\nChoose your Python interpreter in SPELL Runtime Settings.\nOpen a procedure with explicit SPELL imports, then choose Run or Debug.\n\nUse SPELL line breakpoints to pause and inspect variables.\nRun files are saved under .openbexi/runs in your project.");
        help.setFont(javax.swing.UIManager.getFont("Label.font"));
        help.setBorder(javax.swing.BorderFactory.createEmptyBorder(12, 12, 12, 12));
        help.setEditable(false); help.setLineWrap(true); help.setWrapStyleWord(true); help.setOpaque(false);
        DefaultActionGroup group = new DefaultActionGroup();
        for (String id : new String[]{"OpenBEXI.Spell.Run", "OpenBEXI.Spell.Debug", "OpenBEXI.Spell.Settings"}) group.add(ActionManager.getInstance().getAction(id));
        var toolbar = ActionManager.getInstance().createActionToolbar("OpenBEXI.Spell.ToolWindow", group, true);
        toolbar.setTargetComponent(panel);
        panel.add(toolbar.getComponent(), BorderLayout.NORTH); panel.add(help, BorderLayout.CENTER);
        window.getContentManager().addContent(ContentFactory.getInstance().createContent(panel, "", false));
    }
}
