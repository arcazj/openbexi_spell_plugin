// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.intellij.openapi.components.PersistentStateComponent;
import com.intellij.openapi.components.State;
import com.intellij.openapi.components.Storage;
import com.intellij.openapi.project.Project;

@State(name="OpenBexiSpell", storages=@Storage("openbexi-spell.xml"))
public final class SpellSettings implements PersistentStateComponent<SpellSettings.Values> {
    public static final class Values {
        public String interpreter = "";
        public String image = "openbexi-spell-host:0.3.1-dev3";
        public String arguments = "{}";
    }
    private Values values = new Values();
    public static SpellSettings get(Project project) { return project.getService(SpellSettings.class); }
    @Override public Values getState() { return values; }
    @Override public void loadState(Values state) { values = state; }
}
