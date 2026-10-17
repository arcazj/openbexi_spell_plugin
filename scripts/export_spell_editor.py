"""Export editor-only SPELL definitions from the configured native Docker image.

This file is deliberately standalone so the IntelliJ plugin can bundle it. It
never installs a package, imports SPELL, or adds anything to Python's path.
Generated .pyi files describe existing names; unknown names stay unresolved.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile

SCHEMA = "openbexi.spell.editor/1"
GENERATOR_VERSION = 1

# Read installed sources without importing a package or executing a procedure.
# The container receives no host mount, network, or writable root filesystem.
EXTRACT = r'''
import hashlib, json, pathlib, sysconfig, zipfile
root = pathlib.Path(sysconfig.get_path('purelib'))
package = root / 'spell'
if not (package / 'lang/functions.py').is_file():
    raise SystemExit('The selected image has no installed native SPELL language sources')
files = {}
def add(name, data):
    files[name] = {'source': data.decode('utf-8-sig'), 'sha256': hashlib.sha256(data).hexdigest()}
for path in sorted(package.rglob('*.py')):
    add(path.relative_to(root).as_posix(), path.read_bytes())
provenance = root / 'spell_native/provenance'
for name in ('helper_namespace.cpp', 'executor_environment.cpp', 'executor_proc.cpp',
             'dta_module.cpp', 'dta_container_bindings.cpp', 'dta_variable_bindings.cpp'):
    path = provenance / 'source_port/native' / name
    if not path.is_file():
        raise SystemExit('Missing native binding provenance: ' + name)
    add('native/' + name, path.read_bytes())
archive = provenance / 'SPELL2.6.10-src.zip'
with zipfile.ZipFile(archive) as source:
    for name in ('lib/SPELL_EXC/src/SPELLstepPython.C', 'lib/SPELL_EXC/src/SPELLgotoPython.C'):
        add('upstream/' + name, source.read(name))
print(json.dumps({'files': files, 'python': sysconfig.get_python_version()}, ensure_ascii=True))
'''


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (path.is_absolute() or not path.parts or any(p in ('', '.', '..') for p in path.parts)
            or '\\' in name or ':' in name):
        raise ValueError("Unsafe generated path: " + name)
    return path


def statements(body):
    """Expose statically declared conditional definitions, never execute them."""
    for node in body:
        if isinstance(node, ast.If):
            yield from statements(node.body)
            yield from statements(node.orelse)
        elif isinstance(node, (ast.Try, ast.TryStar)):
            yield from statements(node.body)
            for handler in node.handlers:
                yield from statements(handler.body)
            yield from statements(node.orelse)
            yield from statements(node.finalbody)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            yield from statements(node.body)
        else:
            yield node


def literal_type(value):
    if isinstance(value, ast.Constant):
        return {bool: 'bool', int: 'int', float: 'float', str: 'str', bytes: 'bytes',
                type(None): '_SpellAny'}.get(type(value.value), '_SpellAny')
    if isinstance(value, (ast.BinOp, ast.UnaryOp)):
        try:
            literal = ast.literal_eval(value)
            return {int: 'int', float: 'float', str: 'str'}.get(type(literal), '_SpellAny')
        except (ValueError, TypeError):
            return '_SpellAny'
    return {ast.Dict: 'dict', ast.List: 'list', ast.Tuple: 'tuple', ast.Set: 'set'}.get(type(value), '_SpellAny')


def signature(node, method=False):
    args = copy.deepcopy(node.args)
    for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs,
                *([args.vararg] if args.vararg else []), *([args.kwarg] if args.kwarg else [])]:
        if arg.annotation is None and not (method and arg.arg in ('self', 'cls')):
            arg.annotation = ast.Name(id='_SpellAny', ctx=ast.Load())
    args.defaults = [ast.Constant(value=Ellipsis) for _ in args.defaults]
    args.kw_defaults = [ast.Constant(value=Ellipsis) if default is not None else None
                        for default in args.kw_defaults]
    return ast.unparse(args)


def generate_stub(source: str, name: str) -> str:
    """Keep declarations, real imports, signatures and docs; discard execution."""
    tree = ast.parse(source, filename=name)
    header = [
        '# Generated editor-only definition. This is not an executable SPELL runtime.',
        '# Source: ' + name,
        '# SPDX-License-Identifier: GPL-3.0-or-later AND LGPL-3.0-or-later',
        'from typing import Any as _SpellAny',
    ]
    # Keep upstream notices on modules whose licenses are comment headers.
    for line in source.splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            break
        if line.lstrip().startswith('#'):
            header.append(line)
    module_doc = ast.get_docstring(tree, clean=False)
    if module_doc:
        header.append(repr(module_doc))

    def render(body, indent='', class_body=False):
        result = []
        nodes = list(statements(body))
        declared = {node.name for node in nodes if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        known_classes = {node.name for node in nodes if isinstance(node, ast.ClassDef)}
        seen = set()
        for node in nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module == '__future__':
                    continue
                imported = copy.deepcopy(node)
                # Stub imports need explicit same-name aliases to be re-exports.
                for alias in imported.names:
                    if alias.asname is None and alias.name != '*' and '.' not in alias.name:
                        alias.asname = alias.name
                result.append(indent + ast.unparse(imported))
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Do not turn dynamic fallbacks into a blanket Any escape hatch.
                if node.name in ('__getattr__', '__getattribute__') or node.name in seen:
                    continue
                seen.add(node.name)
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id in ('staticmethod', 'classmethod', 'property'):
                        result.append(indent + '@' + decorator.id)
                returns = ast.unparse(node.returns) if node.returns else ('None' if node.name == '__init__' else '_SpellAny')
                prefix = 'async ' if isinstance(node, ast.AsyncFunctionDef) else ''
                result.append(indent + prefix + 'def ' + node.name + '(' + signature(node, class_body) + ') -> ' + returns + ':')
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    result.append(indent + '    ' + repr(doc))
                result.append(indent + '    ...')
                continue
            if isinstance(node, ast.ClassDef):
                if node.name in seen:
                    continue
                seen.add(node.name)
                bases = ', '.join(ast.unparse(base) for base in node.bases)
                result.append(indent + 'class ' + node.name + ('(' + bases + ')' if bases else '') + ':')
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    result.append(indent + '    ' + repr(doc))
                members = render(node.body, indent + '    ', True)
                # Instance fields actually assigned by native Python source.
                attributes = sorted({child.targets[0].attr for child in ast.walk(node)
                    if isinstance(child, ast.Assign) and len(child.targets) == 1
                    and isinstance(child.targets[0], ast.Attribute)
                    and isinstance(child.targets[0].value, ast.Name)
                    and child.targets[0].value.id == 'self'})
                existing = {child.name for child in statements(node.body)
                            if isinstance(child, (ast.FunctionDef, ast.ClassDef))}
                members.extend(indent + '    ' + attr + ': _SpellAny' for attr in attributes if attr not in existing)
                result.extend(members or [indent + '    ...'])
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if not isinstance(target, ast.Name) or target.id in seen:
                        continue
                    label = target.id
                    if label.startswith('__') and label != '__all__':
                        continue
                    seen.add(label)
                    value = node.value
                    if label == '__all__':
                        try:
                            exported = ast.literal_eval(value)
                            if isinstance(exported, (list, tuple)) and all(isinstance(x, str) for x in exported):
                                result.append(indent + '__all__ = ' + repr(exported))
                        except (ValueError, TypeError):
                            pass
                    elif isinstance(value, ast.Name) and value.id in declared:
                        result.append(indent + label + ' = ' + value.id)
                    else:
                        annotation = ast.unparse(node.annotation) if isinstance(node, ast.AnnAssign) else literal_type(value)
                        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in known_classes:
                            annotation = value.func.id
                        result.append(indent + label + ': ' + annotation)
        return result

    lines = header + render(tree.body)
    # Native constants deliberately export exactly these two lazy symbols.
    if name == 'spell/lang/constants.py':
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == '__getattr__':
                supported = next((item for item in ast.walk(node) if isinstance(item, ast.Set)
                                  and {x.value for x in item.elts if isinstance(x, ast.Constant)} == {'DataContainer', 'Var'}), None)
                if supported is not None:
                    lines.append('from libSPELL_DTA_v3 import DataContainer as DataContainer, Var as Var')
    output = '\n'.join(lines) + '\n'
    ast.parse(output, filename=name + 'i')
    return output


def native_stubs(files):
    """Describe the explicit native bindings, guarded by shipped source evidence."""
    required = {
        'native/helper_namespace.cpp': ['PyImport_AddModule("spell.runtime")'],
        'native/executor_environment.cpp': ['helper.install(args.get(),"ARGS")', 'helper.install(variables.get(),"IVARS")'],
        'native/executor_proc.cpp': ['PyDict_New()', 'DatabaseConstants::PROC'],
        'native/dta_module.cpp': ['"DataContainer"', '"Var"'],
        'native/dta_container_bindings.cpp': ['"|s:DataContainer"', '"OO:set"', '"O:get"'],
        'native/dta_variable_bindings.cpp': ['Expected no positional arguments'],
        'upstream/lib/SPELL_EXC/src/SPELLstepPython.C': ['install(Step,"Step")'],
        'upstream/lib/SPELL_EXC/src/SPELLgotoPython.C': ['install(Goto,"Goto")'],
    }
    for path, markers in required.items():
        source = files.get(path, {}).get('source', '')
        if any(marker not in source for marker in markers):
            raise ValueError('Unsupported native binding provenance: ' + path)
    header = '# Editor-only explicit native bindings; see manifest.json for source hashes.\n# SPDX-License-Identifier: GPL-3.0-or-later\nfrom typing import Any as _SpellAny, Iterator as _SpellIterator\n'
    return {
        'spell/runtime.pyi': header + '''from libSPELL_DTA_v3 import DataContainer as DataContainer
def Step(identifier: str, description: str, /) -> None: ...
def Goto(identifier: str, /) -> None: ...
ARGS: DataContainer
IVARS: DataContainer
PROC: dict[str, _SpellAny]
''',
        'libSPELL_DTA_v3.pyi': header + '''class DataContainer:
    def __init__(self, name: str = ..., /) -> None: ...
    def __len__(self) -> int: ...
    def __getitem__(self, key: str | int | float) -> _SpellAny: ...
    def __setitem__(self, key: str | int | float, value: _SpellAny) -> None: ...
    def __iter__(self) -> _SpellIterator[str | int | float]: ...
    def set(self, key: str | int | float, value: _SpellAny, /) -> None: ...
    def get(self, key: str | int | float, /) -> _SpellAny: ...
    def keys(self) -> list[str | int | float]: ...
    def values(self) -> list[_SpellAny]: ...
    def has_key(self, key: str | int | float, /) -> bool: ...
    def enableNotifications(self) -> None: ...
    def disableNotifications(self) -> None: ...
class Var:
    def __init__(self, **modifiers: _SpellAny) -> None: ...
''',
    }


def build_definitions(payload, image_id, requested_image):
    files = payload['files']
    output = {}
    sources = {}
    for name, row in sorted(files.items()):
        safe_relative(name)
        if not isinstance(row['source'], str) or not isinstance(row['sha256'], str):
            raise ValueError('Invalid source record: ' + name)
        sources[name] = row['sha256']
        if name.startswith('spell/') and name.endswith('.py'):
            target = name + 'i'
            output[target] = generate_stub(row['source'], name).encode('utf-8')
    output.update({name: source.encode('utf-8') for name, source in native_stubs(files).items()})
    manifest = {
        'schema': SCHEMA, 'generator_version': GENERATOR_VERSION,
        'generator_sha256': sha(Path(__file__).read_bytes()),
        'image_id': image_id, 'requested_image': requested_image,
        'python_version': payload['python'],
        'purpose': 'Editor indexing only; execute procedures with the native SPELL host.',
        'source_sha256': sources,
        'generated_sha256': {name: sha(data) for name, data in sorted(output.items())},
        'dynamic_exports': {'spell.runtime': ['Step', 'Goto', 'ARGS', 'IVARS', 'PROC'],
                            'libSPELL_DTA_v3': ['DataContainer', 'Var']},
        'limitations': ['Return types use Any where the original source does not declare a type.',
                       'Internal dynamically created exports and arbitrary runtime-added names are not synthesized.'],
    }
    output['manifest.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode('utf-8')
    return output, manifest


def redirected(path: Path) -> bool:
    # Windows directory junctions are reparse points, but not symbolic links.
    return path.is_symlink() or path.is_junction()


def output_boundary(output: Path) -> Path:
    lexical = output.absolute()
    # Inspect the lexical path before resolve() erases links and junctions.
    # Reject redirected ancestors even when the final output does not yet exist.
    for path in (lexical, *lexical.parents):
        if redirected(path):
            raise ValueError('Editor output path contains a symlink or junction: ' + str(path))
    return lexical.resolve()


def existing_output_files(output: Path) -> set[str]:
    result = set()
    pending = [output]
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            if redirected(path):
                raise ValueError('Editor output contains a symlink or junction: ' + str(path))
            if path.is_dir():
                pending.append(path)
            elif path.is_file():
                result.add(path.relative_to(output).as_posix())
            else:
                raise ValueError('Editor output contains an unsupported filesystem entry: ' + str(path))
    return result


def write_definitions(output: Path, files):
    output = output_boundary(output)
    if output == output.parent:
        raise ValueError('Invalid editor output directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    output_boundary(output)
    previous = None
    if output.exists():
        # Walk without following redirects before opening even the manifest.
        actual = existing_output_files(output)
        manifest_path = output / 'manifest.json'
        if not manifest_path.is_file():
            raise ValueError('Refusing to replace an existing directory without an editor manifest: ' + str(output))
        old = json.loads(manifest_path.read_text(encoding='utf-8'))
        if old.get('schema') != SCHEMA:
            raise ValueError('Refusing to replace an unrelated output directory')
        expected = set(old.get('generated_sha256', {})) | {'manifest.json'}
        if actual != expected:
            raise ValueError('Output contains unrecognized files; choose a new editor directory')
        for name, digest in old['generated_sha256'].items():
            safe_relative(name)
            if sha((output / name).read_bytes()) != digest:
                raise ValueError('Output contains locally edited definitions; choose a new editor directory')
    stage = Path(tempfile.mkdtemp(prefix=output.name + '-stage-', dir=output.parent))
    try:
        for name, data in files.items():
            target = stage.joinpath(*safe_relative(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if output.exists():
            previous = Path(tempfile.mkdtemp(prefix=output.name + '-previous-', dir=output.parent))
            previous.rmdir()
            output.rename(previous)
        try:
            stage.rename(output)
        except BaseException:
            if previous is not None:
                previous.rename(output)
                previous = None
            raise
    finally:
        # Both temporary paths were created as siblings immediately above.
        for temporary in (stage, previous):
            if temporary is not None and temporary.exists():
                if temporary.resolve().parent != output.parent:
                    raise ValueError('Temporary directory escaped output parent')
                shutil.rmtree(temporary)
    return output


def export(image: str, output: Path):
    inspected = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}', image],
                               check=True, capture_output=True, text=True, timeout=30)
    image_id = inspected.stdout.strip()
    if len(image_id) != 71 or not image_id.startswith('sha256:') or any(c not in '0123456789abcdef' for c in image_id[7:]):
        raise ValueError('Docker did not return a valid immutable image ID')
    extracted = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--read-only',
                               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                               '--entrypoint', 'python', image_id, '-I', '-c', EXTRACT],
                              check=True, capture_output=True, text=True, encoding='utf-8', timeout=90)
    payload = json.loads(extracted.stdout)
    definitions, manifest = build_definitions(payload, image_id, image)
    root = write_definitions(output, definitions)
    return {'root': str(root), 'image_id': image_id, 'modules': len(manifest['generated_sha256']),
            'manifest': str(root / 'manifest.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = export(args.image, args.output)
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as error:
        detail = getattr(error, 'stderr', '') or ''
        print('SPELL editor synchronization failed: ' + str(error) + ('\n' + detail if detail else ''), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
