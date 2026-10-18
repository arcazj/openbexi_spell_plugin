// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.google.gson.*;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Duration;
import java.util.concurrent.CompletableFuture;

/** Read-only, paged access to the server's durable as-run records. */
final class SpellRecords {
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    private final String url, credential;
    private String token;
    SpellRecords(String endpoint) throws Exception {
        JsonObject config = JsonParser.parseString(Files.readString(Path.of(endpoint))).getAsJsonObject();
        url = config.get("url").getAsString(); credential = config.get("monitor").getAsString();
    }
    private JsonElement request(String path, String key, String body) throws Exception {
        var request = HttpRequest.newBuilder(URI.create(url + path)).timeout(Duration.ofSeconds(10))
            .header("Authorization", "Bearer " + key).header("Content-Type", "application/json");
        if (body != null) request.POST(HttpRequest.BodyPublishers.ofString(body));
        var response = http.send(request.build(), HttpResponse.BodyHandlers.ofString());
        JsonElement value = JsonParser.parseString(response.body());
        if (response.statusCode() != 200) throw new java.io.IOException(value.getAsJsonObject().get("error").getAsString());
        return value;
    }
    synchronized JsonArray read(String id, String path, int line, long after, boolean latest) throws Exception {
        // A fresh read-only connection also handles expiry while an item dialog
        // has been left idle. It never claims execution authority.
        token = request("/api/connect", credential, "{\"name\":\"JetBrains item information\"}").getAsJsonObject().get("client").getAsString();
        try {
            return request("/api/events?id=" + id + "&path=" + URLEncoder.encode(path, StandardCharsets.UTF_8)
                + "&line=" + line + "&after=" + after + "&latest=" + latest, token, null).getAsJsonArray();
        } finally {
            try { request("/api/disconnect", token, "{}"); } catch (Exception ignored) { }
        }
    }
}
