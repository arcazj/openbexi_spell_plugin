// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.google.gson.*;
import com.intellij.execution.ExecutionException;
import com.intellij.execution.configurations.GeneralCommandLine;
import com.intellij.execution.process.ProcessHandler;
import com.intellij.execution.process.ProcessOutputTypes;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

final class DapClient extends ProcessHandler {
    private final Process process;
    private final Map<Integer, CompletableFuture<JsonObject>> pending = new ConcurrentHashMap<>();
    private final AtomicBoolean closing = new AtomicBoolean();
    private int sequence;
    private Consumer<JsonObject> events;
    private final ByteArrayOutputStream inputLine = new ByteArrayOutputStream();
    volatile boolean inputPending;

    DapClient(GeneralCommandLine command) throws ExecutionException { process = command.createProcess(); }
    void begin(Consumer<JsonObject> listener) {
        events = listener;
        // XDebuggerManager owns startNotify for this debug process handler.
        Thread.ofVirtual().name("spell-dap-output").start(this::readMessages);
        Thread.ofVirtual().name("spell-dap-errors").start(() -> {
            try (var reader = new InputStreamReader(process.getErrorStream(), StandardCharsets.UTF_8)) {
                char[] block = new char[4096]; int count;
                while ((count = reader.read(block)) >= 0) notifyTextAvailable(new String(block, 0, count), ProcessOutputTypes.STDERR);
            } catch (IOException error) { if (!closing.get()) report(error); }
        });
    }
    synchronized CompletableFuture<JsonObject> request(String command, JsonObject arguments) {
        int id = ++sequence;
        var future = new CompletableFuture<JsonObject>();
        pending.put(id, future);
        future.orTimeout(30, TimeUnit.SECONDS).whenComplete((value, error) -> pending.remove(id));
        JsonObject message = new JsonObject();
        message.addProperty("seq", id); message.addProperty("type", "request"); message.addProperty("command", command);
        message.add("arguments", arguments);
        try {
            byte[] body = message.toString().getBytes(StandardCharsets.UTF_8);
            if (body.length > 4 * 1024 * 1024) throw new IOException("DAP request exceeds 4 MiB");
            var output = process.getOutputStream();
            output.write(("Content-Length: " + body.length + "\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
            output.write(body); output.flush();
        } catch (IOException error) { future.completeExceptionally(error); }
        return future;
    }
    private void readMessages() {
        try (var input = new BufferedInputStream(process.getInputStream())) {
            for (;;) {
                int length = -1, headerSize = 0;
                for (;;) {
                    var line = new ByteArrayOutputStream();
                    int ch;
                    while ((ch = input.read()) != -1) {
                        if (++headerSize > 8192) throw new IOException("DAP header exceeds 8 KiB");
                        line.write(ch);
                        if (ch == '\n') break;
                    }
                    if (ch == -1) { if (headerSize != 0) throw new EOFException("Incomplete DAP header"); return; }
                    String text = line.toString(StandardCharsets.US_ASCII);
                    if (text.equals("\r\n")) break;
                    int split = text.indexOf(':');
                    if (split < 0) throw new IOException("Malformed DAP header");
                    if (text.substring(0, split).equalsIgnoreCase("Content-Length")) {
                        if (length != -1) throw new IOException("Duplicate DAP length");
                        length = Integer.parseInt(text.substring(split + 1).trim());
                    }
                }
                if (length <= 0 || length > 4 * 1024 * 1024) throw new IOException("Invalid DAP length");
                byte[] body = input.readNBytes(length);
                if (body.length != length) throw new EOFException("Incomplete DAP body");
                JsonObject message = JsonParser.parseString(new String(body, StandardCharsets.UTF_8)).getAsJsonObject();
                if (message.get("type").getAsString().equals("response")) {
                    var future = pending.remove(message.get("request_seq").getAsInt());
                    if (future != null) {
                        if (message.get("success").getAsBoolean()) future.complete(message.getAsJsonObject("body"));
                        else future.completeExceptionally(new IOException(message.has("message") ? message.get("message").getAsString() : "Native request failed"));
                    }
                } else if (message.get("type").getAsString().equals("event")) events.accept(message);
            }
        } catch (Exception error) { if (!closing.get()) report(error); }
        finally {
            closing.set(true);
            pending.values().forEach(value -> value.completeExceptionally(new EOFException("SPELL host ended")));
            pending.clear();
            try {
                if (!process.waitFor(10, TimeUnit.SECONDS)) killOwnedProcess();
                notifyProcessTerminated(process.waitFor());
            } catch (InterruptedException error) { Thread.currentThread().interrupt(); killOwnedProcess(); notifyProcessTerminated(1); }
        }
    }
    void report(Throwable error) { notifyTextAvailable("SPELL: " + error.getMessage() + "\n", ProcessOutputTypes.STDERR); }
    void output(String text, boolean error) { notifyTextAvailable(text, error ? ProcessOutputTypes.STDERR : ProcessOutputTypes.STDOUT); }
    @Override protected void destroyProcessImpl() {
        if (!closing.compareAndSet(false, true)) return;
        inputPending = false;
        request("disconnect", object("terminateDebuggee", true));
        Thread.ofVirtual().start(() -> {
            try { if (!process.waitFor(10, TimeUnit.SECONDS)) killOwnedProcess(); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); killOwnedProcess(); }
        });
    }
    private void killOwnedProcess() {
        process.descendants().forEach(ProcessHandle::destroyForcibly);
        process.destroyForcibly();
    }
    @Override protected void detachProcessImpl() { destroyProcessImpl(); }
    @Override public boolean detachIsDefault() { return false; }
    @Override public OutputStream getProcessInput() {
        return new OutputStream() {
            @Override public synchronized void write(int value) throws IOException {
                if (!inputPending) return;
                if (inputLine.size() > 65536) throw new IOException("Prompt input exceeds 64 KiB");
                if (value == '\n') {
                    String answer = inputLine.toString(StandardCharsets.UTF_8).replaceFirst("\\r$", "");
                    inputLine.reset(); inputPending = false;
                    request("openbexi/input", object("text", answer)).exceptionally(error -> { report(error); return null; });
                } else inputLine.write(value);
            }
        };
    }
    static JsonObject object(Object... pairs) {
        JsonObject result = new JsonObject(); Gson gson = new Gson();
        for (int i = 0; i < pairs.length; i += 2) result.add((String)pairs[i], gson.toJsonTree(pairs[i + 1]));
        return result;
    }
}
