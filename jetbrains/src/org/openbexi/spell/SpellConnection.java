// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.google.gson.*;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;
import java.util.Locale;
import java.util.concurrent.*;
import java.util.function.Consumer;

/** Connection owns no executor. Selecting a record never claims authority. */
final class SpellConnection implements AutoCloseable {
    final Path endpoint;
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
    private volatile String token = "", url = "";
    private volatile boolean closed;

    SpellConnection(String project, Consumer<JsonObject> snapshot, Consumer<String> disconnected) throws Exception {
        boolean windows = System.getProperty("os.name").startsWith("Windows");
        String normalized = Path.of(project).toRealPath().toString();
        if (windows) normalized = normalized.toLowerCase(Locale.ROOT);
        String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(normalized.getBytes(StandardCharsets.UTF_8))).substring(0, 24);
        String local = System.getenv("LOCALAPPDATA");
        Path home = local == null ? Path.of(System.getProperty("user.home"), ".local", "share") : Path.of(local);
        endpoint = home.resolve("OpenBEXI/procedure-services").resolve(hash).resolve("endpoint.json");
        Thread.ofVirtual().name("spell-workspace-connection").start(() -> {
            long revision = -1;
            while (!closed) {
                try {
                    if (token.isEmpty()) {
                        if (!Files.isRegularFile(endpoint)) { Thread.sleep(750); continue; }
                        var config = JsonParser.parseString(Files.readString(endpoint)).getAsJsonObject();
                        url = config.get("url").getAsString();
                        token = request("/api/connect", config.get("operator").getAsString(), DapClient.object("name", "JetBrains workspace"))
                            .getAsJsonObject().get("client").getAsString();
                    }
                    JsonObject state = request("/api/state", token, null).getAsJsonObject();
                    if (revision != state.get("revision").getAsLong()) {
                        revision = state.get("revision").getAsLong(); snapshot.accept(state);
                    }
                    Thread.sleep(750);
                } catch (Exception error) {
                    revision = -1; token = ""; disconnected.accept(error.getMessage());
                    try { Thread.sleep(1500); } catch (InterruptedException ignored) { return; }
                }
            }
            if (!token.isEmpty()) try { request("/api/disconnect", token, new JsonObject()); } catch (Exception ignored) { }
        });
    }
    private JsonElement request(String path, String key, JsonObject body) throws Exception {
        var request = HttpRequest.newBuilder(URI.create(url + path)).timeout(Duration.ofSeconds(body == null ? 4 : 45))
            .header("Authorization", "Bearer " + key).header("Content-Type", "application/json");
        if (body != null) request.POST(HttpRequest.BodyPublishers.ofString(body.toString()));
        var response = http.send(request.build(), HttpResponse.BodyHandlers.ofString());
        JsonElement value = JsonParser.parseString(response.body());
        if (response.statusCode() != 200) throw new java.io.IOException(value.getAsJsonObject().get("error").getAsString());
        return value;
    }
    CompletableFuture<JsonObject> command(String path, JsonObject body) {
        var future = new CompletableFuture<JsonObject>();
        Thread.ofVirtual().start(() -> {
            try { future.complete(request(path, token, body).getAsJsonObject()); }
            catch (Exception error) { future.completeExceptionally(error); }
        });
        return future;
    }
    @Override public void close() { closed = true; }
}
