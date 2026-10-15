"""Tokenizer preparation only; native runtime acceptance remains separate."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('legacy_compare_syntax',
    Path(__file__).resolve().parents[1] / 'source_port/legacy_compare_syntax.py')
syntax = importlib.util.module_from_spec(spec)
spec.loader.exec_module(syntax)


@pytest.mark.parametrize('source,expected', [
    ('result = 1 <> 2\n', True),
    ('result = 0 <> False\n', False),
    ('result = [] <> []\n', False),
    ('result = 1 <> 2 <> 3 and 1 != 2\n', True),
    ('result = (\n 1 <> 2\n)\n', True),
    ('result = 1 \\\n <> 2\n', True),
    ('# <>\nvalue = "<>"\nresult = value <> "other"\n', True),
    ('café = "<>"; result = café <> "other"\n', True),
    ('result = f"{1 <> 2} <>"\n', 'True <>'),
    ('def check():\n return 1 <> 2\nresult = check()\n', True),
])
def test_literal_results_without_changing_comments_strings_or_line_positions(source, expected):
    raw = source.encode('utf-8')
    actual = syntax.normalize(raw)
    assert len(actual) == len(raw)
    assert actual.count(b'\n') == raw.count(b'\n')
    namespace = {}
    exec(compile(actual, 'legacy.py', 'exec'), namespace)
    assert namespace['result'] == expected


@pytest.mark.parametrize('raw', [b'', b'result = 1 != 2\n', b'text = "<>"\n',
    b'text = r"<>"\n# <>\n', b'text = """before\n<>\nafter"""\n',
    'text = "\u2028<>"\n'.encode('utf-8'), b'result = f"literal <> {1 != 2}"\n'])
def test_valid_modern_source_is_byte_preserved(raw):
    assert syntax.normalize(raw) == raw


@pytest.mark.parametrize('raw', [b'x = 1 < > 2\n', b'x = 1 <> (\n',
    b'x = "unterminated <>\n', b'# coding: unknown-codec\nx = 1 <> 2\n'])
def test_invalid_grammar_keeps_compiler_failure_and_then_recovers(raw):
    assert syntax.normalize(raw) == raw
    with pytest.raises(SyntaxError):
        compile(syntax.normalize(raw), 'bad.py', 'exec')
    namespace = {}
    exec(compile(syntax.normalize(b'result = 2 <> 3\n'), 'good.py', 'exec'), namespace)
    assert namespace['result'] is True


@pytest.mark.parametrize('encoding,prefix,newline', [('utf-8', '', '\r\n'),
    ('utf-8-sig', '', '\n'), ('latin-1', '# coding: latin-1\n', '\n')])
def test_encoding_and_newline_bytes_survive(encoding, prefix, newline):
    raw = (prefix + 'café = "<>"; result = café <> "other"' + newline).encode(encoding)
    expected = (prefix + 'café = "<>"; result = café != "other"' + newline).encode(encoding)
    assert syntax.normalize(raw) == expected
