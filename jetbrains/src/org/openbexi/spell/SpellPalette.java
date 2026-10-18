// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import java.awt.Color;
import java.util.Locale;

/** Default colors from SPELL GUI User Manual 2.4.4, page 38. */
final class SpellPalette {
    static final Color CURRENT = new Color(0x0000ff);
    static Color procedure(String status) {
        String state = status.toUpperCase(Locale.ROOT).split(" \\(", 2)[0];
        return new Color(switch (state) {
            case "STARTING", "LOADED" -> 0xe0e0e0;
            case "RUNNING" -> 0xb9ffd7;
            case "WAITING", "INTERRUPTED" -> 0xffffb3;
            case "PROMPT" -> 0xffff00;
            case "PAUSED" -> 0xe0ffc1;
            case "ERROR", "FAILED", "ABORTED" -> 0xffb9b9;
            case "FINISHED" -> 0xdcb9ff;
            case "RELOADING" -> 0xe1feba;
            default -> 0xffffff;
        });
    }
    static Color result(String status) {
        return switch (status.toUpperCase(Locale.ROOT).split(" \\(", 2)[0]) {
            case "SUCCESS" -> new Color(0x00ff00);
            case "FAILED", "ERROR" -> new Color(0xff0000);
            case "IN PROGRESS", "WARNING" -> new Color(0xffff00);
            default -> null;
        };
    }
}
