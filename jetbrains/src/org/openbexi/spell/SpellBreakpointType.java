// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.vfs.VirtualFile;
import com.intellij.xdebugger.breakpoints.XBreakpointProperties;
import com.intellij.xdebugger.breakpoints.XLineBreakpointType;

public final class SpellBreakpointType extends XLineBreakpointType<SpellBreakpointType.Properties> {
    public static final class Properties extends XBreakpointProperties<Properties> {
        @Override public Properties getState() { return this; }
        @Override public void loadState(Properties values) {}
    }
    public SpellBreakpointType() { super("openbexi-spell-line", "SPELL Line Breakpoint"); }
    @Override public Properties createBreakpointProperties(VirtualFile file, int line) { return new Properties(); }
    @Override public boolean canPutAt(VirtualFile file, int line, Project project) { return "py".equalsIgnoreCase(file.getExtension()); }
}
