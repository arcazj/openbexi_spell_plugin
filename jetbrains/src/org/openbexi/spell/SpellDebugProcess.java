// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.google.gson.*;
import com.intellij.execution.ExecutionException;
import com.intellij.execution.configurations.GeneralCommandLine;
import com.intellij.execution.filters.TextConsoleBuilderFactory;
import com.intellij.execution.process.ProcessHandler;
import com.intellij.execution.ui.ExecutionConsole;
import com.intellij.openapi.application.ApplicationManager;
import com.intellij.openapi.fileTypes.FileType;
import com.intellij.openapi.fileTypes.FileTypes;
import com.intellij.openapi.vfs.LocalFileSystem;
import com.intellij.openapi.vfs.VirtualFile;
import com.intellij.ui.ColoredTextContainer;
import com.intellij.ui.SimpleTextAttributes;
import com.intellij.xdebugger.*;
import com.intellij.xdebugger.breakpoints.*;
import com.intellij.xdebugger.evaluation.XDebuggerEditorsProvider;
import com.intellij.xdebugger.frame.*;
import java.util.*;
import java.util.concurrent.CompletableFuture;

public final class SpellDebugProcess extends XDebugProcess {
    private final DapClient client;
    private final VirtualFile program;
    private final Set<XLineBreakpoint<SpellBreakpointType.Properties>> breakpoints = new LinkedHashSet<>();
    private volatile boolean configured;
    private final XBreakpointHandler<XLineBreakpoint<SpellBreakpointType.Properties>> breakpointHandler = new XBreakpointHandler<>(SpellBreakpointType.class) {
        @Override public void registerBreakpoint(XLineBreakpoint<SpellBreakpointType.Properties> breakpoint) {
            breakpoints.add(breakpoint);
            if (configured) updateFile(breakpoint.getFileUrl());
        }
        @Override public void unregisterBreakpoint(XLineBreakpoint<SpellBreakpointType.Properties> breakpoint, boolean temporary) {
            breakpoints.remove(breakpoint);
            if (configured) updateFile(breakpoint.getFileUrl());
        }
    };
    public SpellDebugProcess(XDebugSession session, GeneralCommandLine command, VirtualFile program) throws ExecutionException {
        super(session); this.program = program; client = new DapClient(command);
    }
    private void ui(Runnable work) {
        ApplicationManager.getApplication().invokeLater(() -> { if (!getSession().getProject().isDisposed()) work.run(); });
    }
    private void fail(Throwable error) { client.report(error); ui(() -> getSession().stop()); }
    @Override public XDebuggerEditorsProvider getEditorsProvider() {
        return new XDebuggerEditorsProvider() {
            @Override public FileType getFileType() { return FileTypes.PLAIN_TEXT; }
            @Override public boolean isEvaluateExpressionFieldEnabled() { return false; }
        };
    }
    @Override public XBreakpointHandler<?>[] getBreakpointHandlers() { return new XBreakpointHandler<?>[]{breakpointHandler}; }
    @Override protected ProcessHandler doGetProcessHandler() { return client; }
    @Override public ExecutionConsole createConsole() {
        var console = TextConsoleBuilderFactory.getInstance().createBuilder(getSession().getProject()).getConsole();
        console.attachToProcess(client); return console;
    }
    @Override public void sessionInitialized() {
        getSession().setPauseActionSupported(true);
        client.begin(this::event);
        client.request("initialize", DapClient.object("adapterID", "spell", "linesStartAt1", true, "pathFormat", "path"))
            .thenCompose(ignored -> client.request("launch", DapClient.object("project", getSession().getProject().getBasePath(),
                "program", program.getPath(), "args", List.of(SpellSettings.get(getSession().getProject()).getState().arguments))))
            .exceptionally(error -> { fail(error); return null; });
    }
    private void event(JsonObject message) {
        String event = message.get("event").getAsString();
        JsonObject body = message.has("body") ? message.getAsJsonObject("body") : new JsonObject();
        switch (event) {
            case "initialized" -> ui(this::configure);
            case "output" -> client.output(body.get("output").getAsString(), body.has("category") && body.get("category").getAsString().equals("stderr"));
            case "openbexi/inputRequest" -> {
                client.inputPending = true;
                client.output(body.get("text").getAsString() + "\nChoices: " + body.get("choices").getAsString() + "\nEnter the native option index:\n", false);
            }
            case "stopped" -> client.request("stackTrace", DapClient.object("threadId", 1))
                .thenAccept(stack -> ui(() -> showStack(stack.getAsJsonArray("stackFrames"))))
                .exceptionally(error -> { fail(error); return null; });
            case "continued" -> ui(() -> getSession().sessionResumed());
            case "exited" -> client.output("SPELL finished with exit " + body.get("exitCode").getAsInt() + "\n", false);
            case "terminated" -> ui(() -> getSession().stop());
            default -> { }
        }
    }
    private void configure() {
        for (var breakpoint : XDebuggerManager.getInstance(getSession().getProject()).getBreakpointManager().getBreakpoints(SpellBreakpointType.class))
            if (breakpoint.isEnabled()) breakpoints.add(breakpoint);
        Set<String> files = new LinkedHashSet<>();
        for (var breakpoint : breakpoints) files.add(breakpoint.getFileUrl());
        var requests = files.stream().map(this::updateFile).toArray(CompletableFuture[]::new);
        CompletableFuture.allOf(requests).thenCompose(ignored -> {
            configured = true;
            return client.request("configurationDone", new JsonObject());
        }).exceptionally(error -> { fail(error); return null; });
    }
    private CompletableFuture<JsonObject> updateFile(String url) {
        var selected = breakpoints.stream().filter(value -> value.isEnabled() && value.getFileUrl().equals(url)).toList();
        String path = com.intellij.openapi.vfs.VfsUtilCore.urlToPath(url);
        var request = DapClient.object("source", Map.of("path", path), "breakpoints",
            selected.stream().map(value -> Map.of("line", value.getLine() + 1)).toList());
        var result = client.request("setBreakpoints", request);
        result.thenAccept(response -> ui(() -> {
            JsonArray verified = response.getAsJsonArray("breakpoints");
            for (int i = 0; i < selected.size(); i++) {
                if (verified.get(i).getAsJsonObject().get("verified").getAsBoolean()) getSession().setBreakpointVerified(selected.get(i));
                else getSession().setBreakpointInvalid(selected.get(i), "No executable line in this source");
            }
        })).exceptionally(error -> { client.report(error); return null; });
        return result;
    }
    private void control(String command) {
        client.request(command, DapClient.object("threadId", 1)).exceptionally(error -> { client.report(error); return null; });
    }
    @Override public void startPausing() { control("pause"); }
    @Override public void startStepInto(XSuspendContext context) { control("stepIn"); }
    @Override public void startStepOver(XSuspendContext context) { control("next"); }
    @Override public void startStepOut(XSuspendContext context) { getSession().reportError("The native SPELL adapter does not support Step Out"); }
    @Override public void resume(XSuspendContext context) { control("continue"); }
    @Override public void stop() { client.destroyProcess(); }

    private void showStack(JsonArray values) {
        List<XStackFrame> frames = new ArrayList<>();
        for (JsonElement value : values) frames.add(new Frame(value.getAsJsonObject()));
        XExecutionStack execution = new XExecutionStack("SPELL procedure") {
            @Override public XStackFrame getTopFrame() { return frames.isEmpty() ? null : frames.getFirst(); }
            @Override public void computeStackFrames(int first, XStackFrameContainer container) {
                container.addStackFrames(frames.subList(Math.min(first, frames.size()), frames.size()), true);
            }
        };
        getSession().positionReached(new XSuspendContext() {
            @Override public XExecutionStack getActiveExecutionStack() { return execution; }
            @Override public XExecutionStack[] getExecutionStacks() { return new XExecutionStack[]{execution}; }
        });
    }
    private final class Frame extends XStackFrame {
        private final JsonObject value;
        Frame(JsonObject value) { this.value = value; }
        @Override public XSourcePosition getSourcePosition() {
            VirtualFile file = LocalFileSystem.getInstance().findFileByPath(value.getAsJsonObject("source").get("path").getAsString().replace('\\', '/'));
            return file == null ? null : XDebuggerUtil.getInstance().createPosition(file, value.get("line").getAsInt() - 1);
        }
        @Override public void customizePresentation(ColoredTextContainer container) {
            container.append(value.get("name").getAsString() + ":" + value.get("line").getAsInt(), SimpleTextAttributes.REGULAR_ATTRIBUTES);
        }
        @Override public void computeChildren(XCompositeNode node) {
            if (value.get("id").getAsInt() != 1) { node.addChildren(XValueChildrenList.EMPTY, true); return; }
            client.request("variables", DapClient.object("variablesReference", 1)).thenAccept(response -> ui(() -> {
                XValueChildrenList children = new XValueChildrenList();
                for (JsonElement entry : response.getAsJsonArray("variables")) children.add(new Variable(entry.getAsJsonObject()));
                node.addChildren(children, true);
            })).exceptionally(error -> { ui(() -> node.setErrorMessage(error.getMessage())); return null; });
        }
    }
    private final class Variable extends XNamedValue {
        private final JsonObject value;
        Variable(JsonObject value) { super(value.get("name").getAsString()); this.value = value; }
        @Override public void computePresentation(XValueNode node, XValuePlace place) {
            node.setPresentation(null, value.get("type").getAsString(), value.get("value").getAsString(), false);
        }
        @Override public XValueModifier getModifier() {
            return new XValueModifier() {
                @Override public String getInitialValueEditorText() { return value.get("value").getAsString(); }
                @Override public void setValue(XExpression expression, XModificationCallback callback) {
                    client.request("setVariable", DapClient.object("variablesReference", 1, "name", getName(), "value", expression.getExpression()))
                        .thenAccept(ignored -> ui(() -> { callback.valueModified(); getSession().rebuildViews(); }))
                        .exceptionally(error -> { ui(() -> callback.errorOccurred(error.getMessage())); return null; });
                }
            };
        }
    }
}
