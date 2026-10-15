"""Resolve the preserved p79 has_key label against its actual SCDB contract."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tarfile

from database_import_cases import CASES
from installed_provenance import verify_capture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
from run_language_regressions import validate_report

CONTRACT = 'CMP-LRM244-METHOD-DICTIONARY-HAS-KEY'
DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(path, image):
    raw = json.loads(path.read_bytes())
    validate_report(path, image, len(CASES))
    assert set(raw['checks']) == set(CASES)
    runtime = raw['runtime_sources']['integrated']
    assert runtime is not None
    verify_capture(runtime, raw['inputs'], raw.get('lf_normalized_inputs'))
    source = 'spell/lib/adapter/databases/dbfile.py'
    assert raw['runtime_sources']['installed'][source] == runtime['python_sources'][source]
    inventory = json.loads((ROOT / 'conformance/inventory.json').read_bytes())
    item, = [row for row in inventory['rows'] if row['id'] == CONTRACT]
    assert item['name'] == 'dict.has_key' and item['pages'] == '79' and item['package'] == 'PY'
    manual = ROOT / 'docs/reference/SPELL - Language Reference - 2.4.4.pdf'
    assert sha(manual) == 'ed13fae748997a48d6930ac40a30fb31f8b54119be0005a0431a1920613801c3'
    archive_path = path.parent / 'workspace.tar'
    checks = {}
    with tarfile.open(archive_path) as archive:
        members = {row.name.removeprefix('./'): row for row in archive.getmembers() if row.isfile()}
        captured_checks = json.loads(archive.extractfile(members['checks.json']).read())
        assert captured_checks == raw['checks']
        for dimension in DIMENSIONS:
            name = 'spacecraft-existence:' + dimension
            row, spec = raw['checks'][name], CASES[name]
            assert row['passed'] and all(row[key] == value for key, value in spec.items()), name
            project = name.replace(':', '-')
            procedure = archive.extractfile(members[project + '/data/Procedures/main.py']).read().decode('utf-8')
            assert spec['source'] in procedure and 'from spell.runtime import GDB, SCDB' in procedure
            assert archive.extractfile(members[project + '/data/SpacecraftDB/SCDB.DB']).read().decode('utf-8') == spec['spacecraft']
            native_log = archive.extractfile(members[project + '/native.log']).read()
            assert b'CONFIGURED_DATABASE_PASSED' in native_log and b'[ STATUS  ] FINISHED' in native_log
            assert b'AddressSanitizer:' not in native_log and b'runtime error:' not in native_log
            check = deepcopy(row)
            check.update(observed_contracts=row['contracts'], contracts=[CONTRACT],
                oracle='LRM p79 Example 137 uses the original SCDB.has_key method; independently loaded configured databases and literal True/False/TypeError expectations.',
                legacy_spelling_supported=True)
            checks[name] = check
    inputs = {**raw['inputs'], **{name: sha(ROOT / name) for name in (
        'conformance/database_scope_report.py', 'conformance/DATABASE_SCOPE.md')}}
    return dict(passed=True, runtime_image=raw['runtime_image'], inputs=inputs, checks=checks,
        qualified_contracts=[CONTRACT],
        manual_resolution={'inventory': item, 'documented_callable': 'SCDB.has_key', 'page': 79,
            'reason': 'Historical label abbreviates the database dictionary API; the authoritative example uses SCDB, not a built-in dict.',
            'builtin_dict_has_key_supported': False},
        raw={'path': str(path.resolve()), 'sha256': sha(path), 'workspace_sha256': sha(archive_path)},
        scope='Original page-79 database existence method only; explicit-import native profile',
        full_v05_accepted=False, full_v06_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    report = qualify(args.raw, args.image)
    output = ROOT / 'conformance/evidence/database_scope.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': str(output), 'contracts': 1, 'checks': len(report['checks'])}))


if __name__ == '__main__':
    main()
