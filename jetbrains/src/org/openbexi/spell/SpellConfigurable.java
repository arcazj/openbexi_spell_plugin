// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.google.gson.JsonParser;
import com.intellij.openapi.options.Configurable;
import com.intellij.openapi.options.ConfigurationException;
import com.intellij.openapi.project.Project;
import com.intellij.util.ui.FormBuilder;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.swing.*;

public final class SpellConfigurable implements Configurable {
    private final Project project;
    private final JTextField interpreter = new JTextField(36);
    private final JTextField image = new JTextField(36);
    private final JTextField arguments = new JTextField(36);
    public SpellConfigurable(Project project) { this.project = project; }
    @Override public String getDisplayName() { return "SPELL Runtime"; }
    @Override public JComponent createComponent() {
        reset();
        return FormBuilder.createFormBuilder()
            .addLabeledComponent("CPython 3.13 executable:", interpreter)
            .addLabeledComponent("Native Docker image:", image)
            .addLabeledComponent("Procedure arguments (JSON object):", arguments)
            .addComponent(new JLabel("Install openbexi-spell-host in this interpreter first."))
            .addComponentFillVertically(new JPanel(), 0).getPanel();
    }
    @Override public boolean isModified() {
        var values = SpellSettings.get(project).getState();
        return !interpreter.getText().equals(values.interpreter) || !image.getText().equals(values.image)
            || !arguments.getText().equals(values.arguments);
    }
    @Override public void reset() {
        var values = SpellSettings.get(project).getState();
        interpreter.setText(values.interpreter); image.setText(values.image); arguments.setText(values.arguments);
    }
    @Override public void apply() throws ConfigurationException {
        try {
            if (!Files.isRegularFile(Path.of(interpreter.getText()))) throw new IllegalArgumentException("Select an existing CPython executable");
            if (image.getText().isBlank()) throw new IllegalArgumentException("Specify the native image");
            if (!JsonParser.parseString(arguments.getText()).isJsonObject()) throw new IllegalArgumentException("Arguments must be a JSON object");
            var values = new SpellSettings.Values();
            values.interpreter = interpreter.getText(); values.image = image.getText(); values.arguments = arguments.getText();
            SpellSettings.get(project).loadState(values);
        } catch (RuntimeException error) { throw new ConfigurationException(error.getMessage()); }
    }
}
