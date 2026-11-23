// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.google.gson.*;
import com.intellij.openapi.Disposable;
import com.intellij.openapi.actionSystem.AnActionEvent;
import com.intellij.openapi.application.PathManager;
import com.intellij.openapi.fileChooser.FileChooser;
import com.intellij.openapi.fileChooser.FileChooserDescriptor;
import com.intellij.openapi.project.DumbAwareAction;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.util.Key;
import com.intellij.openapi.wm.*;
import com.intellij.ui.content.ContentFactory;
import java.awt.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import javax.swing.*;
import javax.swing.table.DefaultTableModel;

public final class SpellGatewayWindow implements ToolWindowFactory {
    private static final String ID = "SPELL Server";
    private static final Key<View> VIEW = Key.create("org.openbexi.spell.gateway.view");

    @Override public void createToolWindowContent(Project project, ToolWindow window) {
        var view = new View(project);
        project.putUserData(VIEW, view);
        var content = ContentFactory.getInstance().createContent(view, "v0.8 server", false);
        content.setDisposer(view);
        window.getContentManager().addContent(content);
    }

    static boolean blocksLocal(Project project) {
        var view = project.getUserData(VIEW);
        return view != null && view.remoteMode;
    }

    public static final class Open extends DumbAwareAction {
        @Override public void actionPerformed(AnActionEvent event) {
            var project = event.getProject();
            if (project != null) {
                var window = ToolWindowManager.getInstance(project).getToolWindow(ID);
                if (window != null) window.activate(null);
            }
        }
    }

    public static final class View extends JPanel implements Disposable {
        private static final String BOOTSTRAP =
            "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('openbexi_spell_gateway',run_name='__main__')";
        private final Project project;
        private final ExecutorService executor = Executors.newSingleThreadExecutor(Thread.ofVirtual().factory());
        private final JButton connect = new JButton("Connect"), disconnect = new JButton("Disconnect");
        private final JButton refresh = new JButton("Refresh"), reserve = new JButton("Reserve"), start = new JButton("Start native");
        private final JComboBox<String> contexts = new JComboBox<>(), procedures = new JComboBox<>();
        private final JLabel status = new JLabel("Disconnected"), binding = new JLabel();
        private final Map<String, JButton> commands = new LinkedHashMap<>();
        private final DefaultTableModel model = new DefaultTableModel(
            new String[]{"Execution", "Procedure", "Owner", "Control", "Lifecycle", "Native result"}, 0) {
            @Override public boolean isCellEditable(int row, int col) { return false; }
        };
        private final JTable records = new JTable(model);
        private JsonObject snapshot = new JsonObject();
        private volatile boolean remoteMode, disposed;
        private volatile Process bridge;
        private BufferedReader input;
        private BufferedWriter output;
        private boolean busy, rendering;

        View(Project project) {
            super(new BorderLayout(6, 6));
            this.project = project;
            var connection = new JPanel(new FlowLayout(FlowLayout.LEADING));
            for (Component c : new Component[]{connect, disconnect, new JLabel("Context"), contexts, refresh, status}) connection.add(c);
            var catalog = new JPanel(new FlowLayout(FlowLayout.LEADING));
            for (Component c : new Component[]{new JLabel("Approved procedure"), procedures, reserve, binding}) catalog.add(c);
            var heading = new JPanel(new GridLayout(2, 1));
            heading.add(connection); heading.add(catalog); add(heading, BorderLayout.NORTH);
            records.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);
            add(new JScrollPane(records), BorderLayout.CENTER);
            var actions = new JPanel(new FlowLayout(FlowLayout.LEADING)); actions.add(start);
            String[][] labels = {{"CMD_RUN","Run / Continue"},{"CMD_STEP","Step"},{"CMD_PAUSE","Pause"},{"CMD_ABORT","Abort"},{"CMD_CLOSE","Close native"}};
            for (String[] entry : labels) {
                var button = new JButton(entry[1]); commands.put(entry[0], button); actions.add(button);
                button.addActionListener(event -> send(entry[0], selectedId()));
            }
            add(actions, BorderLayout.SOUTH);
            connect.addActionListener(event -> {
                var descriptor = new FileChooserDescriptor(true, false, false, false, false, false);
                descriptor.setTitle("Select SPELL v0.8 connection JSON");
                var file = FileChooser.chooseFile(descriptor, project, null);
                if (file != null) connect(Path.of(file.getPath()));
            });
            disconnect.addActionListener(event -> disconnect());
            refresh.addActionListener(event -> send("refresh", null));
            contexts.addActionListener(event -> { if (!rendering && !busy && remoteMode) send("refresh", null); });
            procedures.addActionListener(event -> { if (!rendering) updateButtons(); });
            records.getSelectionModel().addListSelectionListener(event -> { if (!rendering) updateButtons(); });
            reserve.addActionListener(event -> send("reserve", (String)procedures.getSelectedItem()));
            start.addActionListener(event -> send("start", selectedId()));
            updateButtons();
        }

        public void connect(Path file) {
            if (busy || remoteMode || disposed) return;
            String interpreter = SpellSettings.get(project).getState().interpreter;
            if (interpreter.isBlank() || !Files.isRegularFile(Path.of(interpreter))) {
                status.setText("Select the installed CPython in SPELL Runtime settings."); return;
            }
            remoteMode = true;
            submit("Connecting", () -> {
                var jar = PathManager.getJarPathForClass(SpellGatewayWindow.class);
                if (jar == null) throw new IOException("Cannot locate the installed SPELL plugin JAR");
                var process = new ProcessBuilder(interpreter, "-I", "-B", "-u", "-X", "utf8", "-c", BOOTSTRAP,
                    jar, file.toAbsolutePath().toString()).redirectError(ProcessBuilder.Redirect.DISCARD).start();
                bridge = process;
                if (disposed) { process.destroy(); throw new IOException("Workspace closed"); }
                input = process.inputReader(StandardCharsets.UTF_8);
                output = process.outputWriter(StandardCharsets.UTF_8);
                return read();
            }, data -> {
                rendering = true;
                try {
                    contexts.removeAllItems();
                    for (var item : data.getAsJsonArray("contexts")) contexts.addItem(item.getAsString());
                } finally { rendering = false; }
                if (contexts.getItemCount() > 0) send("refresh", null);
                else status.setText("Connected. No contexts are available.");
            });
        }

        private JsonObject read() throws IOException {
            String line = input.readLine();
            if (line == null) throw new EOFException("Gateway client stopped. Check the installed IDE wheel and connection file.");
            var data = JsonParser.parseString(line).getAsJsonObject();
            if (data.has("error")) throw new IOException(data.get("error").getAsString());
            return data;
        }

        private void submit(String label, Callable<JsonObject> operation, java.util.function.Consumer<JsonObject> onSuccess) {
            busy = true; status.setText(label); updateButtons();
            executor.execute(() -> {
                try {
                    var value = operation.call();
                    SwingUtilities.invokeLater(() -> {
                        if (disposed) return;
                        busy = false; onSuccess.accept(value); updateButtons();
                    });
                } catch (Exception error) {
                    SwingUtilities.invokeLater(() -> {
                        if (disposed) return;
                        busy = false; snapshot = new JsonObject(); status.setText(error.getMessage()); updateButtons();
                    });
                }
            });
        }

        private void send(String operation, String id) {
            if (busy || !remoteMode || disposed || contexts.getSelectedItem() == null) return;
            var request = new JsonObject();
            request.addProperty("context", (String)contexts.getSelectedItem());
            request.addProperty("operation", operation);
            if (id != null) request.addProperty("id", id);
            String previous = selectedId();
            submit(operation.equals("refresh") ? "Refreshing" : "Waiting for server", () -> {
                output.write(request.toString()); output.newLine(); output.flush();
                return read();
            }, data -> render(data, data.has("selected") ? data.get("selected").getAsString() : previous));
        }

        private void render(JsonObject data, String selected) {
            snapshot = data;
            var old = procedures.getSelectedItem();
            rendering = true;
            try {
                procedures.removeAllItems();
                for (var element : data.getAsJsonArray("procedures"))
                    procedures.addItem(element.getAsJsonObject().get("procedure_id").getAsString());
                if (old != null && ((DefaultComboBoxModel<String>)procedures.getModel()).getIndexOf(old) >= 0)
                    procedures.setSelectedItem(old);
                model.setRowCount(0);
                for (var element : data.getAsJsonArray("executions")) {
                    var row = element.getAsJsonObject();
                    String id = row.get("id").getAsString();
                    model.addRow(new Object[]{id, row.get("procedure").getAsString(), row.get("owner").getAsString(),
                        row.get("control").getAsString(), row.get("lifecycle").getAsString(),
                        row.get("native_result").isJsonNull() ? "" : row.get("native_result").getAsString()});
                    if (id.equals(selected)) records.setRowSelectionInterval(model.getRowCount()-1, model.getRowCount()-1);
                }
                String message = "Connected as " + data.get("subject").getAsString();
                if (!data.get("catalog_available").getAsBoolean()) message += " · source catalog unavailable (404)";
                status.setText(message);
            } finally { rendering = false; }
        }

        private String selectedId() {
            int row = records.getSelectedRow();
            return row < 0 ? null : (String)model.getValueAt(row, 0);
        }

        private void updateButtons() {
            boolean idle = !busy && remoteMode;
            connect.setEnabled(!busy && !remoteMode); disconnect.setEnabled(idle);
            contexts.setEnabled(idle); refresh.setEnabled(idle && contexts.getSelectedItem() != null);
            procedures.setEnabled(idle); reserve.setEnabled(idle && procedures.getSelectedItem() != null
                && snapshot.has("reserve") && snapshot.get("reserve").getAsBoolean());
            binding.setText("");
            if (snapshot.has("procedures")) for (var element : snapshot.getAsJsonArray("procedures")) {
                var item = element.getAsJsonObject();
                if (item.get("procedure_id").getAsString().equals(procedures.getSelectedItem()))
                    binding.setText(item.get("entrypoint").getAsString() + " @ " + item.get("source_revision").getAsString());
            }
            start.setEnabled(false); commands.values().forEach(button -> button.setEnabled(false));
            int row = records.getSelectedRow();
            if (idle && snapshot.has("executions") && row >= 0 && row < snapshot.getAsJsonArray("executions").size()) {
                var entry = snapshot.getAsJsonArray("executions").get(row).getAsJsonObject();
                start.setEnabled(entry.get("start").getAsBoolean());
                for (var command : entry.getAsJsonArray("commands")) {
                    var button = commands.get(command.getAsString());
                    if (button != null) button.setEnabled(true);
                }
            }
        }

        private static void close(Process process) {
            if (process == null) return;
            try {
                process.getOutputStream().close();
                if (!process.waitFor(8, TimeUnit.SECONDS)) process.destroy();
            } catch (IOException ignored) { process.destroy(); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); process.destroy(); }
        }

        private void disconnect() {
            if (busy || !remoteMode) return;
            submit("Disconnecting", () -> { close(bridge); bridge = null; return new JsonObject(); }, ignored -> {
                remoteMode = false; snapshot = new JsonObject(); rendering = true;
                try { contexts.removeAllItems(); procedures.removeAllItems(); model.setRowCount(0); }
                finally { rendering = false; }
                status.setText("Disconnected");
            });
        }

        @Override public void dispose() {
            disposed = true;
            project.putUserData(VIEW, null);
            executor.shutdownNow();
            Thread.ofVirtual().start(() -> close(bridge));
        }
    }
}
