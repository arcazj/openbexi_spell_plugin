// SPDX-License-Identifier: GPL-3.0-or-later
// Generated from source_port/legacy_compare_syntax.py; checked byte-for-byte.
#ifndef OPENBEXI_V08_LEGACY_SYNTAX_H
#define OPENBEXI_V08_LEGACY_SYNTAX_H
static constexpr char v08LegacySyntax[] = R"v08_legacy("""Preserve source layout while recognizing SPELL's legacy not-equal token.

SPDX-License-Identifier: GPL-3.0-or-later
This helper is not yet installed or connected to the native compiler.
"""
import io
import tokenize


def normalize(source):
    if b'<>' not in source:
        return source
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(source).readline)
        text = source.decode(encoding)
        tokens = list(tokenize.tokenize(io.BytesIO(source).readline))
    except (SyntaxError, UnicodeError, tokenize.TokenError):
        return source  # Preserve the compiler's own malformed-source diagnostic.
    if any(token.type == tokenize.ERRORTOKEN for token in tokens):
        return source
    lines = text.split('\n')
    changed = False
    for index, token in enumerate(tokens):
        if token.type != tokenize.OP:
            continue
        end = token.end
        if token.string != '<>':
            # CPython can tokenize the legacy spelling as two adjacent modern
            # operators. Whitespace or a line boundary must not form a token.
            if token.string != '<' or index + 1 >= len(tokens):
                continue
            following = tokens[index + 1]
            if (following.type != tokenize.OP or following.string != '>'
                    or token.end != following.start):
                continue
            end = following.end
        row, column = token.start
        assert end == (row, column + 2)
        assert lines[row - 1][column:column + 2] == '<>'
        lines[row - 1] = lines[row - 1][:column] + '!=' + lines[row - 1][column + 2:]
        changed = True
    return '\n'.join(lines).encode(encoding) if changed else source
)v08_legacy";
#endif
