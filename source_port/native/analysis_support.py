"""CPython 3.13 metadata for original SPELL analyzers. SPDX-License-Identifier: GPL-3.0-or-later."""
import ast
import dis
import io
from pathlib import Path
import tokenize
import types
import weakref

_sources = {}


def _forget(identity, reference, entries):
    current = entries.get(identity)
    if current is not None and current[0] is reference:
        entries.pop(identity)


def _code_tree(code):
    yield code
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            yield from _code_tree(value)


def remember(code, source):
    if isinstance(source, bytes):
        encoding, _ = tokenize.detect_encoding(io.BytesIO(source).readline)
        source = source.decode(encoding)
    for child in _code_tree(code):
        # Code equality can ignore filenames and non-executable source changes.
        # Bind by identity; the weak callback must not retain the code object.
        identity = id(child)
        reference = weakref.ref(child, lambda ref, key=identity, entries=_sources, forget=_forget: forget(key, ref, entries))
        _sources[identity] = (reference, source)


def _source(code):
    entry = _sources.get(id(code))
    if entry is not None and entry[0]() is code:
        return entry[1]
    try:
        with tokenize.open(code.co_filename) as stream:
            source = stream.read()
    except (OSError, UnicodeError) as error:
        raise ValueError('Original source is unavailable for bytecode analysis') from error
    # Imported Python files use their original text. SPELL's file reader also
    # appends its legacy exit-name sentinel; match the actual compiled code.
    normalized = source.replace('\r\n', '\n')
    spell_source = (normalized if normalized.endswith('\n') else normalized + '\n') + 'exit' if normalized else normalized
    for candidate in (source, spell_source):
        compiled = compile(candidate, code.co_filename, 'exec', dont_inherit=True)
        if any(child == code for child in _code_tree(compiled)):
            remember(code, candidate)
            return candidate
    raise ValueError('Source differs from the executing code; analysis refused')


def _scope(tree, code):
    if code.co_name == '<module>':
        return tree
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            if node.name == code.co_name and first == code.co_firstlineno:
                matches.append(node)
    if len(matches) == 1:
        return matches[0]
    if code.co_name in ('<lambda>', '<genexpr>', '<listcomp>', '<setcomp>', '<dictcomp>'):
        return None  # Expression scopes have no statement/try nodes of their own.
    raise ValueError('Cannot identify the original source scope of this code object')


def _nodes(scope):
    if scope is None:
        return
    for child in ast.iter_child_nodes(scope):
        yield child
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            yield from _nodes(child)


def describe(code):
    source = _source(code)
    tree = ast.parse(source, filename=code.co_filename)
    scope = _scope(tree, code)
    instructions = list(dis.get_instructions(code))
    rows = {}
    previous = None
    ignored = {'RESUME', 'COPY_FREE_VARS', 'MAKE_CELL', 'RETURN_GENERATOR'}
    for instruction in instructions:
        line = instruction.positions.lineno
        if line is None or line <= 0 or instruction.opname in ignored:
            previous = instruction
            continue
        row = rows.setdefault(line, [line, instruction.offset, instruction.opcode, True, False, False])
        if instruction.opname == 'RETURN_CONST' or (
                instruction.opname == 'RETURN_VALUE' and previous is not None
                and previous.opname in ('LOAD_CONST', 'LOAD_FAST', 'LOAD_FAST_CHECK')):
            row[5] = True
        previous = instruction
    blocks = []
    simple = (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr, ast.Return, ast.Raise,
              ast.Assert, ast.Delete, ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)
    for node in _nodes(scope):
        if isinstance(node, simple):
            for line in range(node.lineno, node.end_lineno):
                if line in rows:
                    rows[line][4] = True
        if isinstance(node, (ast.Try, ast.TryStar)):
            start = node.body[0].lineno
            end = node.body[-1].end_lineno
            active = [line for line in rows if start <= line <= end]
            if not active:
                continue
            handlers = [(h.body[0].lineno, h.end_lineno) for h in node.handlers]
            final = (node.finalbody[0].lineno, node.finalbody[-1].end_lineno) if node.finalbody else (0, 0)
            blocks.append((node.lineno, start, max(active), node.end_lineno, handlers, final))
    # Nested blocks take precedence when asking where the current try ends.
    blocks.sort(key=lambda block: (block[3] - block[0], -block[0]))
    return (list(rows.values()), blocks,
            max((i.offset for i in instructions), default=-1), max(rows, default=-1))
