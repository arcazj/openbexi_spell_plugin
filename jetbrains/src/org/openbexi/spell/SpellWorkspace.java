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
    }
    public static final class Session {
        public final VirtualFile file;
        public final String mode;
        public final Instant started = Instant.now();
        public final String[] source;
        public final Map<Integer, LineResult> lines = new LinkedHashMap<>();
        public final StringBuilder output = new StringBuilder();
        public String status = "Starting", error = "";
        public String rootProcedureId = "";
        public Instant ended;
        public Integer exitCode;
        public JsonObject prompt;
        public boolean answering, stopRequested, reminded;
        public int currentLine = -1;
        private final DapClient client;
        private Session(VirtualFile file, String mode, DapClient client) {
            this.file = file; this.mode = mode; this.client = client;
            var document = FileDocumentManager.getInstance().getDocument(file);
            source = document == null ? new String[]{"Source unavailable"} : document.getText().split("\\R", -1);
        }
        public boolean active() { return ended == null; }
    }
    private final Project project;
    private final List<Session> sessions = new ArrayList<>();
    private final List<Runnable> listeners = new ArrayList<>();
    private Session selected;
    public SpellWorkspace(Project project) { this.project = project; }
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
        var window = ToolWindowManager.getInstance(project).getToolWindow("SPELL");
        if (window != null) window.show();
    }
    void event(Session session, String event, JsonObject body) {
        ui(() -> {
            if (body.has("rootProcedureId")) session.rootProcedureId = string(body, "rootProcedureId");
            switch (event) {
                case "initialized", "continued" -> session.status = "Running";
                case "stopped" -> session.status = "Paused";
                case "spell/prompt" -> {
                    session.prompt = body.deepCopy(); session.answering = false; session.reminded = false;
                    session.error = "";
                    if (session.rootProcedureId.isBlank() || string(body, "ProcId").equals(session.rootProcedureId)) session.status = "Prompt";
                    selected = session; show();
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
        if (!session.rootProcedureId.isBlank() && !string(fields, "ProcId").equals(session.rootProcedureId)) return;
        // Only associate records with a source line when the runtime supplies an exact source path.
        if (!body.has("source") || !body.has("line")) return;
        String path = string(body.getAsJsonObject("source"), "path").replace('\\', '/');
        if (!session.file.getPath().equalsIgnoreCase(path)) return;
        int line = body.get("line").getAsInt();
        if (line < 1 || line > session.source.length) return;
        LineResult result = session.lines.computeIfAbsent(line, ignored -> new LineResult());
        String type = string(fields, "DataType");
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
        session.currentLine = line;
    }
    public CompletableFuture<JsonObject> answer(Session session, String promptId, String answer) {
        if (!session.active() || session.prompt == null || session.answering ||
            !string(session.prompt, "promptId").equals(promptId))
            return CompletableFuture.failedFuture(new IllegalStateException("This prompt is no longer waiting for an answer"));
        session.answering = true; session.error = ""; changed();
        return session.client.answerPrompt(promptId, answer).whenComplete((value, error) -> ui(() -> {
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
        if (session != null && session.active()) {
            session.stopRequested = true; session.status = "Stopping"; session.prompt = null;
            session.client.destroyProcess(); changed();
        }
    }
    public void control(String command) {
        Session session = selected;
        if (session == null || !session.active()) return;
        session.client.request(command, DapClient.object("threadId", 1)).exceptionally(error -> {
            ui(() -> { session.error = error.getMessage(); changed(); }); return null;
        });
    }
    static String string(JsonObject object, String name) {
        return object.has(name) && !object.get(name).isJsonNull() ? object.get(name).getAsString() : "";
    }
    private static String first(JsonObject object, String... names) {
        for (String name : names) { String value = string(object, name); if (!value.isBlank()) return value; }
        return "";
    }
    @Override public void dispose() { for (Session session : sessions) if (session.active()) session.client.destroyProcess(); listeners.clear(); }
}
