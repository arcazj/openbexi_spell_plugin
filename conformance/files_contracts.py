"""LRM pp.90-92 filesystem oracles in the original native executor.

Only owned temporary fixture paths are modified. pathlib/os provide independent
filesystem observations; all language operations use original SPELL helpers.
"""
import json
import os
from pathlib import Path
import uuid

from spell.lang.functions import OpenFile, CloseFile, WriteFile, ReadFile, ReadDirectory, DeleteFile
from spell.lang.constants import READ, WRITE, READ_WRITE, APPEND, REPEAT, SKIP
from spell.lib.adapter.file import File
from spell.lib.exception import DriverException, SyntaxException

PREFIX = 'CMP-LRM244-'
DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')
cases = {}
checks = {}
active = None


def eq(actual, expected):
    assert actual == expected and type(actual) is type(expected), (actual, expected)


def rejects(operation, kind=DriverException):
    try:
        operation()
    except kind:
        return
    raise AssertionError('Expected ' + kind.__name__)


def fixture():
    path = Path('files-owned-' + uuid.uuid4().hex)
    path.mkdir()
    return path


def call(function, *args, **kwargs):
    return function(*args, HandleError=False, **kwargs)


def case(name, contracts, positive, boundary, failure, recovery=None):
    cases[name] = dict(contracts=[PREFIX + item for item in contracts], positive=positive,
        boundary=boundary, failure=failure, recovery=recovery or (lambda: (failure(), positive())),
        oracle='LRM 2.4.4 pp.90-92: independent file bytes, descriptor state, permissions and directory entries; actual original helpers and native executor')


def mode_positive():
    root = fixture()
    p = root/'mode.txt'
    p.write_text('old\n', encoding='utf-8')
    h = call(OpenFile, str(p))
    eq(call(ReadFile, h), ['old\n'])
    call(CloseFile, h)
    h = call(OpenFile, str(p), Mode=READ_WRITE)
    eq(call(ReadFile, h), ['old\n'])
    eq(call(WriteFile, h, 'new'), True)
    call(CloseFile, h)
    eq(p.read_text(), 'new\n')
    h = call(OpenFile, str(p), Mode=APPEND)
    call(WriteFile, h, 'tail')
    call(CloseFile, h)
    eq(p.read_text(), 'new\ntail')
    h = call(OpenFile, str(p), Mode=WRITE)
    call(WriteFile, h, 'fresh')
    call(CloseFile, h)
    eq(p.read_text(), 'fresh')


def mode_boundary():
    p = fixture()/'empty.txt'
    for mode in (WRITE, APPEND):
        h = call(OpenFile, str(p), Mode=mode)
        eq(h.isOpen(), True)
        call(CloseFile, h)
        eq(p.read_bytes(), b'')
    # A relative basename must resolve to the current working directory.
    relative = 'files-basename-' + uuid.uuid4().hex
    h = call(OpenFile, relative, Mode=WRITE)
    call(CloseFile, h)
    eq(Path(relative).read_bytes(), b'')


def mode_failure():
    root = fixture()
    p = root/'absent'
    for mode in (READ, READ_WRITE):
        rejects(lambda: call(OpenFile, str(p), Mode=mode))
        eq(p.exists(), False)
    rejects(lambda: call(OpenFile, str(root), Mode=WRITE))
    rejects(lambda: call(OpenFile, str(p), Mode='not-a-mode'))
    eq(p.exists(), False)
    rejects(lambda: call(OpenFile, 42), SyntaxException)


case('modes', ['CONSTANT-FILE-MODE-APPEND', 'CONSTANT-FILE-MODE-READ',
    'CONSTANT-FILE-MODE-READ-WRITE', 'CONSTANT-FILE-MODE-WRITE', 'MODIFIER-MODE',
    'FUNCTION-OPENFILE', 'EXAMPLE-162', 'SECTION-4-17-1-116'],
    mode_positive, mode_boundary, mode_failure)


def close_positive():
    p = fixture()/'close'
    h = call(OpenFile, str(p), Mode=WRITE)
    eq(h.isOpen(), True)
    assert call(CloseFile, h) is h
    eq(h.isOpen(), False)


def close_boundary():
    h = File(str(fixture()/'unopened'))
    eq(h.isOpen(), False)
    assert call(CloseFile, h) is h
    assert call(CloseFile, h) is h


def close_failure():
    rejects(lambda: call(CloseFile, 'wrong'), SyntaxException)
    rejects(lambda: call(CloseFile, File(str(fixture()))))
    close_positive()


case('close', ['FUNCTION-CLOSEFILE', 'EXAMPLE-163', 'SECTION-4-17-2-117',
    'METHOD-FILE-ISOPEN', 'TYPE-FILEHANDLE'], close_positive, close_boundary, close_failure)


def write_positive():
    p = fixture()/'write'
    h = call(OpenFile, str(p), Mode=WRITE)
    eq(call(WriteFile, h, 'verbatim'), True)
    eq(call(WriteFile, h, ['one', 'two']), True)
    call(CloseFile, h)
    eq(p.read_bytes(), b'verbatimone\ntwo\n')


def write_boundary():
    p = fixture()/'unicode'
    h = call(OpenFile, str(p), Mode=WRITE)
    call(WriteFile, h, '')
    call(WriteFile, h, [])
    call(WriteFile, h, ['café', '', '\u03bb'])
    call(CloseFile, h)
    eq(p.read_bytes(), 'café\n\n\u03bb\n'.encode())


def write_failure():
    p = fixture()/'bad-list'
    h = call(OpenFile, str(p), Mode=WRITE)
    rejects(lambda: call(WriteFile, h, ['prefix', 42]), SyntaxException)
    rejects(lambda: call(WriteFile, h, 42), SyntaxException)
    call(CloseFile, h)
    eq(p.read_bytes(), b'')
    rejects(lambda: call(WriteFile, h, 'closed'))
    h = call(OpenFile, str(p), Mode=READ)
    rejects(lambda: call(WriteFile, h, 'readonly'))
    call(CloseFile, h)
    eq(p.read_bytes(), b'')


case('write', ['FUNCTION-WRITEFILE', 'EXAMPLE-164', 'SECTION-4-17-3-118'],
    write_positive, write_boundary, write_failure)


def read_positive():
    p = fixture()/'read'
    p.write_bytes(b'one\ntwo\nlast')
    h = call(OpenFile, str(p), Mode=READ)
    eq(call(ReadFile, h), ['one\n', 'two\n', 'last'])
    eq(call(ReadFile, h), ['one\n', 'two\n', 'last'])
    call(CloseFile, h)


def read_boundary():
    p = fixture()/'empty'
    p.touch()
    h = call(OpenFile, str(p), Mode=READ_WRITE)
    eq(call(ReadFile, h), [])
    call(CloseFile, h)


def read_failure():
    p = fixture()/'write-only'
    h = call(OpenFile, str(p), Mode=WRITE)
    rejects(lambda: call(ReadFile, h))
    call(CloseFile, h)
    rejects(lambda: call(ReadFile, h))
    rejects(lambda: call(ReadFile, str(p)), SyntaxException)


case('read', ['FUNCTION-READFILE', 'EXAMPLE-165', 'SECTION-4-17-4-119'],
    read_positive, read_boundary, read_failure)


def directory_positive():
    root = fixture()
    (root/'one').touch()
    (root/'two').mkdir()
    eq(sorted(call(ReadDirectory, str(root))), ['one', 'two'])
    eq(sorted(call(ReadDirectory, File(str(root)))), ['one', 'two'])


def directory_boundary():
    eq(call(ReadDirectory, str(fixture())), [])


def directory_failure():
    root = fixture()
    rejects(lambda: call(ReadDirectory, str(root/'absent')))
    p = root/'file'
    p.touch()
    rejects(lambda: call(ReadDirectory, str(p)))
    rejects(lambda: call(ReadDirectory, None), SyntaxException)


case('directory', ['FUNCTION-READDIRECTORY', 'EXAMPLE-166', 'SECTION-4-17-5-120'],
    directory_positive, directory_boundary, directory_failure)


def paths_positive():
    root = fixture()
    p = root/'item'
    p.touch()
    f = File(str(p))
    eq(f.filename(), str(p))
    eq(f.dirname(), str(root))
    eq(f.basename(), 'item')
    eq(f.exists(), True)
    eq(f.isfile(), True)
    eq(f.isdir(), False)
    eq(f.canRead(), True)
    eq(f.canWrite(), True)
    d = File(str(root))
    eq(d.isdir(), True)
    eq(d.isfile(), False)
    appended = d + 'next'
    assert appended is d
    eq(appended.filename(), str(root/'next'))


def paths_boundary():
    f = File('relative')
    eq(f.dirname(), '')
    eq(f.basename(), 'relative')
    f = File(str(fixture())) + File('nested')
    eq(f.basename(), 'nested')
    eq(f.exists(), False)
    eq(f.isfile(), False)
    eq(f.isdir(), False)
    eq(f.canRead(), False)
    eq(f.canWrite(), False)


def paths_failure():
    root = fixture()
    p = root/'permissions'
    p.touch()
    f = File(str(p))
    rejects(lambda: f + 'child')
    rejects(lambda: File(str(root)) + 42)
    p.chmod(0)
    try:
        eq(f.canRead(), False)
        eq(f.canWrite(), False)
        rejects(lambda: call(OpenFile, f))
        rejects(lambda: call(OpenFile, f, Mode=WRITE))
    finally:
        p.chmod(0o600)
    eq(f.canRead(), True)
    eq(f.canWrite(), True)


case('paths', ['FUNCTION-CANDIDATE-FILE', 'TYPE-FILE', 'EXAMPLE-167',
    'METHOD-FILE-BASENAME', 'METHOD-FILE-CANREAD', 'METHOD-FILE-CANWRITE',
    'METHOD-FILE-DIRNAME', 'METHOD-FILE-EXISTS', 'METHOD-FILE-FILENAME',
    'METHOD-FILE-ISDIR', 'METHOD-FILE-ISFILE', 'OPERATOR-FILE-PATH-APPEND',
    'SECTION-4-17-6-121'], paths_positive, paths_boundary, paths_failure)


def delete_positive():
    root = fixture()
    p = root/'file'
    p.touch()
    eq(call(DeleteFile, str(p)), True)
    eq(p.exists(), False)
    p.touch()
    eq(call(DeleteFile, File(str(p))), True)
    eq(p.exists(), False)


def delete_boundary():
    root = fixture()
    empty = root/'empty'
    empty.mkdir()
    eq(call(DeleteFile, File(str(empty))), True)
    eq(empty.exists(), False)


def delete_failure():
    root = fixture()
    p = root/'retained'
    p.write_text('preserved')
    rejects(lambda: call(DeleteFile, str(root)))
    eq(p.read_text(), 'preserved')
    rejects(lambda: call(DeleteFile, str(root/'missing')))
    rejects(lambda: call(DeleteFile, []), SyntaxException)
    p.chmod(0o400)
    try:
        rejects(lambda: call(DeleteFile, str(p)))
        eq(p.exists(), True)
    finally:
        p.chmod(0o600)


case('delete', ['FUNCTION-DELETEFILE', 'EXAMPLE-168', 'SECTION-4-17-7-122'],
    delete_positive, delete_boundary, delete_failure)


def prompt_failure():
    path = fixture()/'repair'
    active['prompts'].append({'choices': ['REPEAT', 'SKIP'], 'answer': 'REPEAT',
                              'repair': str(path)})
    Path('data-files-active.json').write_text(json.dumps(active), encoding='utf-8')
    h = OpenFile(str(path), OnFailure=REPEAT | SKIP)
    eq(call(ReadFile, h), ['controller repaired\n'])
    call(CloseFile, h)


case('error-policy', ['SECTION-4-17-8-123'], prompt_failure, mode_failure,
    read_failure, prompt_failure)


for name, spec in cases.items():
    for dimension in DIMENSIONS:
        identifier = name + ':' + dimension
        active = {'check': identifier, 'prompts': []}
        row = {key: spec[key] for key in ('contracts', 'oracle')}
        row.update(dimension=dimension, passed=False)
        try:
            spec[dimension]()
            row['passed'] = True
        except Exception as error:
            row['error'] = type(error).__name__ + ': ' + str(error)
        row['expected_prompts'] = active['prompts']
        checks[identifier] = row

for dimension in DIMENSIONS:
    checks['file-manipulation:' + dimension] = dict(dimension=dimension,
        contracts=[PREFIX+'SECTION-4-17-115'],
        oracle='LRM 4.17: every constituent opening, closing, write/read, directory, path, deletion and failure-policy oracle must pass',
        passed=all(row['passed'] for row in checks.values() if row['dimension'] == dimension))
    checks['file-manipulation:' + dimension]['expected_prompts'] = []

Path('data-files-results.json').write_text(json.dumps({'schema': 1, 'checks': checks}, indent=2), encoding='utf-8')
