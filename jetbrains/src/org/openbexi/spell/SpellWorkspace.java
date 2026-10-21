// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.google.gson.*;
import com.intellij.execution.process.*;
import com.intellij.openapi.Disposable;
import com.intellij.openapi.application.ApplicationManager;
import com.intellij.openapi.fileEditor.FileDocumentManager;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.util.Key;
import com.intellij.openapi.util.Disposer;
import com.intellij.openapi.vfs.VirtualFile;
import com.intellij.openapi.wm.ToolWindowManager;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.CompletableFuture;

/** Project-owned session state. All presentation state is changed on the EDT. */
public final class SpellWorkspace implements Disposable {
    public static final class LineResult {
        public String time = "", item = "", value = "", result = "";
        public JsonObject fields = new JsonObject();
        public final List<JsonObject> history = new ArrayList<>();
        public int iteration;
    }
    public static final class Session {
        public final VirtualFile file;
        public final String mode;
        public Instant started = Instant.now();
        public String[] source;
        public final Map<String, String> sources = new LinkedHashMap<>();
        public final Map<String, Map<Integer, LineResult>> results = new LinkedHashMap<>();
        public String currentSource = "", selectedSource = "";
        public String serviceId = "", endpoint = "";
        public final Map<Integer, LineResult> lines = new LinkedHashMap<>();
        public final StringBuilder output = new StringBuilder();
        public String status = "Starting", error = "";
        public String rootProcedureId = "";
        public Instant ended;
        public Integer exitCode;
        public JsonObject prompt;
        public boolean answering, stopRequested, reminded;
        public boolean controlling = true;
        public String controller = "IDE", pending = "";
        public String connection = "Connected";
        public int currentLine = -1;
        private final DapClient client;
        private Session(VirtualFile file, String mode, DapClient client) {
            this.file = file; this.mode = mode; this.client = client;
            var document = FileDocumentManager.getInstance().getDocument(file);
            source = document == null ? new String[]{"Source unavailable"} : document.getText().split("\\R", -1);
            selectedSource = currentSource = file.getPath();
            sources.put(selectedSource, String.join("\n", source)); results.put(selectedSource, lines);
        }
        public boolean active() { return ended == null; }
        public String[] shownSource() { return sources.getOrDefault(selectedSource, "").split("\\R", -1); }
        public Map<Integer, LineResult> shownResults() { return results.getOrDefault(selectedSource, Map.of()); }
    }
    private final Project project;
    private final List<Session> sessions = new ArrayList<>();
    private final List<Runnable> listeners = new ArrayList<>();
    private Session selected;
    private final Set<String> previousWindows = new LinkedHashSet<>();
    private boolean focused;
    private SpellConnection connection;
    public SpellWorkspace(Project project) {
        this.project = project;
        if (project.getBasePath() != null) try {
            connection = new SpellConnection(project.getBasePath(), state -> ui(() -> synchronize(state)),
                error -> ui(() -> {
                    for (var session : sessions) if (session.active()) session.connection = "Disconnected";
                    changed();
                }));
        } catch (Exception ignored) { /* Run reports interpreter or project errors. */ }
    }
    public static SpellWorkspace get(Project project) { return project.getService(SpellWorkspace.class); }
    public List<Session> sessions() { return List.copyOf(sessions); }
    public Session selected() { return selected; }
    public void select(Session session) { selected = session; changed(); }
    public void listen(Runnable listener, Disposable owner) {
        listeners.add(listener); Disposer.register(owner, () -> listeners.remove(listener));
    }
    private void ui(Runnable work) {
        if (project.isDisposed()) return;
        if (ApplicationManager.getApplication().isDispatchThread()) work.run();
        else ApplicationManager.getApplication().invokeLater(() -> { if (!project.isDisposed()) work.run(); });
    }
    private void changed() { for (Runnable listener : List.copyOf(listeners)) listener.run(); }
    private void synchronize(JsonObject state) {
        for (var value : state.getAsJsonArray("runs")) {
            JsonObject data = value.getAsJsonObject(); String id = string(data, "id");
            Session session = sessions.stream().filter(item -> item.serviceId.equals(id)).findFirst().orElse(null);
            // The bridge announces its ID after native startup. Do not create a
            // duplicate while that launch is still awaiting acknowledgement.
            if (session == null && sessions.stream().anyMatch(item -> item.serviceId.isBlank() && item.active()
                    && item.file.getPath().replace('\\', '/').equals(string(data, "script").replace('\\', '/')))) continue;
            if (session == null) {
                String script = string(data, "script");
                VirtualFile file = com.intellij.openapi.vfs.LocalFileSystem.getInstance().findFileByPath(script.replace('\\', '/'));
                if (file == null) file = new com.intellij.testFramework.LightVirtualFile(java.nio.file.Path.of(script).getFileName().toString());
                session = new Session(file, string(data, "mode"), null);
                session.serviceId = id; session.started = java.time.OffsetDateTime.parse(string(data, "started")).toInstant();
                sessions.add(session);
            }
            boolean bound = session.client != null && !session.client.isProcessTerminated();
            session.endpoint = connection.endpoint.toString(); session.connection = string(data, "connection");
            if (!bound) session.controlling = data.get("controlling").getAsBoolean();
            session.controller = string(data, "controller"); session.pending = string(data, "pending");
            session.status = string(data, "status"); session.rootProcedureId = string(data, "root_id");
            session.ended = data.get("active").getAsBoolean() ? null : Instant.now();
            session.exitCode = data.get("exit_code").isJsonNull() ? null : data.get("exit_code").getAsInt();
            session.sources.clear();
            for (var source : data.getAsJsonObject("sources").entrySet()) session.sources.put(source.getKey().replace('\\', '/'), source.getValue().getAsString());
            session.currentSource = string(data, "current_path").replace('\\', '/');
            if (session.currentSource.isBlank()) session.currentSource = string(data, "script").replace('\\', '/');
            if (!session.sources.containsKey(session.selectedSource)) session.selectedSource = session.currentSource;
            var current = data.getAsJsonObject("current");
            session.currentLine = current.has(string(data, "current_path")) ? current.get(string(data, "current_path")).getAsInt() : -1;
            session.results.clear();
            for (var source : data.getAsJsonObject("results").entrySet()) {
                var rows = new LinkedHashMap<Integer, LineResult>();
                for (var row : source.getValue().getAsJsonObject().entrySet()) {
                    JsonObject record = row.getValue().getAsJsonObject(); var result = new LineResult();
                    result.time = string(record, "timestamp"); result.item = string(record, "item"); result.value = string(record, "value"); result.result = string(record, "status");
                    if (record.has("details")) result.fields = record.getAsJsonObject("details");
                    rows.put(Integer.parseInt(row.getKey()), result);
                }
                String path = source.getKey().replace('\\', '/');
                if (path.equals(session.file.getPath().replace('\\', '/'))) {
                    session.lines.clear(); session.lines.putAll(rows); session.results.put(path, session.lines);
                } else session.results.put(path, rows);
            }
            session.output.setLength(0); session.output.append(string(data, "output"));
            if (!bound) {
                session.prompt = data.get("prompt").isJsonObject() ? nativePrompt(data.getAsJsonObject("prompt")) : null;
                session.reminded = data.get("reminder").getAsBoolean();
            }
        }
        sessions.sort(Comparator.comparing((Session session) -> session.started).reversed());
        if (selected == null && !sessions.isEmpty()) selected = sessions.getFirst();
        changed();
    }
    private static JsonObject nativePrompt(JsonObject prompt) {
        JsonObject nativeValue = DapClient.object("promptId", string(prompt, "promptId"), "Text", string(prompt, "text"),
            "ProcId", string(prompt, "procedureId"), "DataType", switch (string(prompt, "inputType")) {
                case "password" -> 4096; case "number" -> 16; case "date" -> 1024; default -> 0;
            });
        var labels = new ArrayList<String>();
        for (var choice : prompt.getAsJsonArray("choices")) labels.add(string(choice.getAsJsonObject(), "label"));
        nativeValue.addProperty("OptionValues", String.join("\u0004", labels));
        if (prompt.has("defaultHint")) { nativeValue.addProperty("DefaultProvided", "True"); nativeValue.add("Default", prompt.get("defaultHint")); }
        return nativeValue;
    }
    Session start(VirtualFile file, String mode, DapClient client) {
        Session session = new Session(file, mode, client);
        sessions.addFirst(session); selected = session;
        // Keep active runs, and at most 100 completed runs during this IDE session.
        for (int index = sessions.size() - 1; index >= 100; index--)
            if (!sessions.get(index).active()) sessions.remove(index);
        client.addProcessListener(new ProcessAdapter() {
            @Override public void onTextAvailable(ProcessEvent event, Key type) {
                ui(() -> {
                    session.output.append(event.getText());
                    if (session.output.length() > 524288) session.output.delete(0, session.output.length() - 524288);
                    changed();
                });
            }
            @Override public void processTerminated(ProcessEvent event) {
                ui(() -> {
                    session.ended = Instant.now(); session.prompt = null; session.answering = false;
                    if (session.exitCode == null || event.getExitCode() != 0) session.exitCode = event.getExitCode();
                    session.status = session.stopRequested || session.exitCode == 130 ? "Aborted" : session.exitCode == 0 ? "Finished" : "Failed";
                    changed();
                });
            }
        });
        changed(); show(); return session;
    }
    public void show() {
        var manager = ToolWindowManager.getInstance(project);
        var window = manager.getToolWindow("SPELL");
        if (window == null) return;
        for (String id : manager.getToolWindowIds()) {
            var other = manager.getToolWindow(id);
            if (!id.equals("SPELL") && other != null && other.isVisible()) {
                if (!focused) previousWindows.add(id);
                other.hide();
            }
        }
        focused = true;
        // Showing a tool window can be deferred. Maximize only once its pane
        // exists, and preserve the original size when focus is requested again.
        window.show(() -> {
            if (!project.isDisposed() && focused && window.isVisible() && !manager.isMaximized(window))
                manager.setMaximized(window, true);
        });
    }
    public void restoreLayout() {
        var manager = ToolWindowManager.getInstance(project); var window = manager.getToolWindow("SPELL");
        focused = false;
        if (window != null) {
            // IntelliJ clears the saved maximized size after a manual restore
            // or layout change; restoring it again asserts and then throws.
            if (manager.isMaximized(window)) manager.setMaximized(window, false);
            window.hide();
        }
        for (String id : previousWindows) { var other = manager.getToolWindow(id); if (other != null) other.show(); }
        previousWindows.clear(); manager.activateEditorComponent();
    }
    void event(Session session, String event, JsonObject body) {
        ui(() -> {
            if (body.has("rootProcedureId")) session.rootProcedureId = string(body, "rootProcedureId");
            switch (event) {
                case "openbexi/service" -> { session.serviceId = string(body, "id"); session.endpoint = string(body, "endpoint"); }
                case "openbexi/workspace" -> {
                    session.controlling = body.has("controlling") && body.get("controlling").getAsBoolean();
                    session.controller = string(body, "controller"); session.pending = string(body, "pending");
                    if (session.active()) session.status = string(body, "status");
                }
                case "spell/source" -> {
                    String path = string(body.getAsJsonObject("source"), "path").replace('\\', '/');
                    int offset = body.get("offset").getAsInt();
                    String previous = offset == 0 ? "" : session.sources.getOrDefault(path, "");
                    if (offset == previous.codePointCount(0, previous.length())) session.sources.put(path, previous + string(body, "text"));
                }
                case "initialized", "continued" -> session.status = "Running";
                case "stopped" -> session.status = "Paused";
                case "spell/prompt" -> {
                    session.prompt = body.deepCopy(); session.answering = false; session.reminded = false;
                    session.error = "";
                    if (session.rootProcedureId.isBlank() || string(body, "ProcId").equals(session.rootProcedureId)) session.status = "Prompt";
                    // A prompt marks its procedure; it does not steal history selection.
                }
                case "spell/promptClosed" -> {
                    if (session.prompt != null && string(session.prompt, "promptId").equals(string(body, "promptId"))) {
                        session.prompt = null; session.answering = false;
                    }
                }
                case "openbexi/promptReminder" -> session.reminded = true;
                case "spell/status" -> {
                    JsonObject fields = fields(body);
                    String status = string(fields, "ExecutorStatus");
                    if (!status.isBlank() && string(fields, "ProcId").equals(session.rootProcedureId)) session.status = status;
                    if (!status.equals("PROMPT") && session.prompt != null &&
                        string(fields, "ProcId").equals(string(session.prompt, "ProcId"))) session.prompt = null;
                }
                case "spell/notification" -> notification(session, body);
                case "exited" -> {
                    session.exitCode = body.get("exitCode").getAsInt();
                    session.status = session.exitCode == 0 ? "Finished" : "Failed";
                    session.prompt = null;
                }
                default -> { }
            }
            changed();
        });
    }
    private static JsonObject fields(JsonObject body) {
        return body.has("fields") && body.get("fields").isJsonObject() ? body.getAsJsonObject("fields") : body;
    }
    private void notification(Session session, JsonObject body) {
        JsonObject fields = fields(body);
        // Only associate records with a source line when the runtime supplies an exact source path.
        if (!body.has("source") || !body.has("line")) return;
        String path = string(body.getAsJsonObject("source"), "path").replace('\\', '/');
        if (!session.sources.containsKey(path)) return;
        int line = body.get("line").getAsInt();
        if (line < 1 || line > session.sources.get(path).split("\\R", -1).length) return;
        LineResult result = session.results.computeIfAbsent(path, ignored -> new LinkedHashMap<>()).computeIfAbsent(line, ignored -> new LineResult());
        String type = string(fields, "DataType");
        try { result.iteration = Integer.parseInt(string(fields, "SCount")); }
        catch (NumberFormatException ignored) { if (type.equals("CURRENT_LINE")) result.iteration++; }
        result.history.add(fields.deepCopy());
        if (result.history.size() > 200) result.history.removeFirst();
        if (type.equals("ITEM") || type.equals("CURRENT_LINE") || result.result.isBlank()) {
            result.fields = fields.deepCopy();
            result.time = first(fields, "ItemTime", "Time");
            result.item = first(fields, "ItemName", "Name").replace('\u0004', ' ');
            result.value = first(fields, "ItemValue", "Value").replace('\u0004', ' ');
            result.result = first(fields, "ItemStatus", "Status", "ExecutorStatus").replace('\u0004', ' ');
            if (result.result.isBlank()) result.result = switch (type) {
                case "CURRENT_LINE" -> "Reached"; case "CALL" -> "Call"; case "RETURN" -> "Returned"; default -> type;
            };
        }
        if (type.equals("CURRENT_LINE")) { session.currentLine = line; session.currentSource = path; }
    }
    public CompletableFuture<JsonObject> answer(Session session, String promptId, String answer) {
        if (!session.active() || !session.controlling || !session.connection.equals("Connected") || session.prompt == null || session.answering ||
            !string(session.prompt, "promptId").equals(promptId))
            return CompletableFuture.failedFuture(new IllegalStateException("This prompt is no longer waiting for an answer"));
        session.answering = true; session.error = ""; changed();
        var response = bound(session) ? session.client.answerPrompt(promptId, answer) :
            request(session, "spell/promptAnswer", DapClient.object("promptId", promptId, "value", answer));
        return response.whenComplete((value, error) -> ui(() -> {
            if (session.prompt != null && string(session.prompt, "promptId").equals(promptId)) {
                session.answering = false;
                if (error == null) {
                    if (session.rootProcedureId.isBlank() || string(session.prompt, "ProcId").equals(session.rootProcedureId)) session.status = "Running";
                    session.prompt = null;
                }
                else session.error = error.getMessage();
            }
            changed();
        }));
    }
    public void stop(Session session) {
        if (session != null && session.active() && session.controlling && session.connection.equals("Connected")) {
            session.stopRequested = true; session.status = "Stopping"; session.prompt = null;
            if (bound(session)) session.client.destroyProcess();
            else request(session, "disconnect", DapClient.object("terminateDebuggee", true));
            changed();
        }
    }
    public void control(String command) {
        Session session = selected;
        if (session == null || !session.active() || !session.connection.equals("Connected") || (!session.controlling && !command.equals("openbexi/claim"))) return;
        request(session, command, DapClient.object("threadId", 1)).exceptionally(error -> {
            ui(() -> { session.error = error.getMessage(); changed(); }); return null;
        });
    }
    private static boolean bound(Session session) { return session.client != null && !session.client.isProcessTerminated(); }
    private CompletableFuture<JsonObject> request(Session session, String command, JsonObject arguments) {
        if (bound(session)) return session.client.request(command, arguments);
        if (connection == null) return CompletableFuture.failedFuture(new IllegalStateException("Workspace is disconnected"));
        boolean authority = command.equals("openbexi/claim") || command.equals("openbexi/release");
        return connection.command(authority ? "/api/control" : "/api/command", authority ?
            DapClient.object("id", session.serviceId, "release", command.equals("openbexi/release")) :
            DapClient.object("id", session.serviceId, "command", command, "arguments", arguments));
    }
    static String string(JsonObject object, String name) {
        return object.has(name) && !object.get(name).isJsonNull() ? object.get(name).getAsString() : "";
    }
    private static String first(JsonObject object, String... names) {
        for (String name : names) { String value = string(object, name); if (!value.isBlank()) return value; }
        return "";
    }
    @Override public void dispose() {
        if (connection != null) connection.close();
        for (Session session : sessions) if (bound(session)) session.client.detachProcess();
        listeners.clear();
    }
}
