"""Preserve source layout while recognizing SPELL's legacy not-equal token.

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
    for token in tokens:
        if token.type != tokenize.OP or token.string != '<>':
            continue
        row, column = token.start
        assert token.end == (row, column + 2)
        assert lines[row - 1][column:column + 2] == '<>'
        lines[row - 1] = lines[row - 1][:column] + '!=' + lines[row - 1][column + 2:]
        changed = True
    return '\n'.join(lines).encode(encoding) if changed else source
