"""Join independently executed Python and native compatibility evidence."""
import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from check import DIMENSIONS, supported_check
from installed_provenance import verify_capture
from database_scope_report import qualify as qualify_database
from database_values_composed_report import qualify as qualify_values
from legacy_compare_composed_report import qualify as qualify_comparison

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
from run_language_regressions import validate_report

CONTRACTS = ['CMP-LRM244-SECTION-2-1-001', 'CMP-LRM244-SECTION-2-1-8-009']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def specification():
    # Read the exact checked-in declarative cases without running their oracles
    # or importing the native library into the host interpreter.
    tree = ast.parse((ROOT / 'conformance/python_contracts.py').read_text(encoding='utf-8'))
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Import) and any(item.name.startswith('spell.') for item in node.names)
        or isinstance(node, ast.ImportFrom) and (node.module or '').startswith('spell.')
        or isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name) and node.value.func.id == 'run')]
    namespace = {'__name__': 'python_case_specification'}
    exec(compile(tree, 'python_case_specification', 'exec'), namespace)
    return namespace['cases'], namespace['sections']


def compose(python, supplements):
    cases, sections = specification()
    assert set(python['checks']) == {name + ':' + dimension
        for name in (*cases, *sections) for dimension in DIMENSIONS}
    checks = deepcopy(python['checks'])
    for name, spec in cases.items():
        for dimension in DIMENSIONS:
            row = checks[name + ':' + dimension]
            assert row['passed'] and row['source'] == spec['sources'][dimension]
            assert row['dimension'] == dimension and row['contracts'] == [name]
            assert row['oracle'] == spec['oracle']
            if spec['legacy_spelling_supported'] is False:
                assert row['legacy_spelling_supported'] is False
                assert row['evidence_kind'] == 'migration-and-rejection'
            else:
                assert supported_check(python, name + ':' + dimension, dimension)
    for name, members in sections.items():
        for dimension in DIMENSIONS:
            row = checks[name + ':' + dimension]
            assert row['passed'] and row['contracts'] == [name] and row['dimension'] == dimension
            assert row['dependencies'] == [member + ':' + dimension for member in members]
    expected = {name for name, spec in cases.items() if spec['legacy_spelling_supported'] is False}
    replacements = {}
    for label, report in supplements.items():
        assert report['passed'] and report['runtime_image'] == python['runtime_image']
        contract, = report['qualified_contracts']
        assert contract in expected and contract not in replacements
        replacements[contract] = label
        for dimension in DIMENSIONS:
            key, = [key for key, row in report['checks'].items()
                    if row['contracts'] == [contract] and supported_check(report, key, dimension)]
            row = deepcopy(report['checks'][key])
            assert row.get('legacy_spelling_supported') is True
            row['observation'] = {'report': label, 'check': key}
            checks[contract + ':' + dimension] = row
    assert set(replacements) == expected
    result = {'checks': checks}
    for contract in CONTRACTS:
        for dimension in DIMENSIONS:
            key = contract + ':' + dimension
            assert supported_check(result, key, dimension), key
            checks[key]['oracle'] = (
                'Every declared child retains its independent positive/boundary/failure/recovery '
                'oracle. Native <> evidence replaces migration rejection; SCDB.has_key and '
                'database octal use their documented page-79/page-83 scopes. All use one installed runtime.')
    return checks


def qualify(paths, image):
    assert set(paths) == {'python', 'comparison', 'database', 'values', 'user'}
    python = json.loads(paths['python'].read_bytes())
    validate_report(paths['python'], image, 488)
    runtime = python['runtime_sources']['integrated']
    assert runtime is not None and runtime['driver_composition'] is not None
    verify_capture(runtime, python['inputs'])
    supplements = {
        'comparison': qualify_comparison(paths['comparison'], image),
        'database': qualify_database(paths['database'], image),
        'values': qualify_values(paths['values'], paths['user'], image),
    }
    inputs = dict(python['inputs'])
    for report in supplements.values():
        for name, digest in report['inputs'].items():
            assert name not in inputs or inputs[name] == digest, name
            inputs[name] = digest
    for name in ('conformance/python_sections_report.py', 'tests/test_python_sections_report.py',
                 'conformance/PYTHON_SECTIONS.md'):
        inputs[name] = sha(ROOT / name)
    return dict(passed=True, runtime_image=image, inputs=inputs,
        checks=compose(python, supplements), qualified_contracts=CONTRACTS,
        raw={name: {'path': str(path.resolve()), 'sha256': sha(path)} for name, path in paths.items()},
        supplements={name: {'qualified_contracts': report['qualified_contracts'],
                           'raw': report['raw']} for name, report in supplements.items()},
        scope='LRM sections 2.1 and 2.1.8 in the explicit-import CPython 3.13 native procedure profile',
        limitations=['Imported Python modules and eval/compile retain CPython syntax',
            'Page-79 has_key is SCDB.has_key; page-83 octal is database-file grammar',
            'Native stepping, checkpoints and whole SPELL service families have separate acceptance'],
        full_v05_accepted=False, full_v06_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('python', 'comparison', 'database', 'values', 'user'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    paths = {name: getattr(args, name) for name in ('python', 'comparison', 'database', 'values', 'user')}
    report = qualify(paths, args.image)
    output = ROOT / 'conformance/evidence/python_sections.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(output), contracts=len(CONTRACTS), checks=len(report['checks']))))


if __name__ == '__main__':
    main()
