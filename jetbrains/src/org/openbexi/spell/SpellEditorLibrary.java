// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.google.gson.JsonParser;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.roots.AdditionalLibraryRootsProvider;
import com.intellij.openapi.roots.SyntheticLibrary;
import com.intellij.openapi.vfs.LocalFileSystem;
import com.intellij.openapi.vfs.VirtualFile;
import java.util.Collection;
import java.util.List;
import java.nio.charset.StandardCharsets;

/** An indexing library, not a Python runtime source root or installed package. */
public final class SpellEditorLibrary extends AdditionalLibraryRootsProvider {
    @Override public Collection<SyntheticLibrary> getAdditionalProjectLibraries(Project project) {
        VirtualFile root = root(project);
        return root == null ? List.of() : List.of(SyntheticLibrary.newImmutableLibrary(List.of(root)));
    }
    @Override public Collection<VirtualFile> getRootsToWatch(Project project) {
        VirtualFile root = root(project);
        return root == null ? List.of() : List.of(root);
    }
    private VirtualFile root(Project project) {
        if (project.getBasePath() == null) return null;
        VirtualFile root = LocalFileSystem.getInstance().findFileByPath(project.getBasePath() + "/.openbexi/editor/current");
        if (root == null) return null;
        var manifest = root.findChild("manifest.json");
        if (manifest == null) return null;
        try {
            var data = JsonParser.parseString(new String(manifest.contentsToByteArray(), StandardCharsets.UTF_8)).getAsJsonObject();
            String image = SpellSettings.get(project).getState().image;
            if (!"openbexi.spell.editor/1".equals(data.get("schema").getAsString())) return null;
            return image.equals(data.get("requested_image").getAsString()) || image.equals(data.get("image_id").getAsString()) ? root : null;
        } catch (Exception ignored) { return null; }
    }
}
