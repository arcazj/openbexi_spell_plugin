"""Verify octal diagnostic evidence without promoting an overlaid runtime."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import zipfile

from database_values_cases import CASES
from installed_provenance import verify_capture
from user_database_cases import CASES as USER_CASES, EXAMPLE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
sys.path.insert(0, str(ROOT / 'source_port'))
from run_language_regressions import validate_report
import data_files_patches
import database_import_patches
import user_database_patches
import database_values_patches as patch


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path):
    return {'path': str(path.resolve()), 'sha256': sha(path)}


def verify_archive(path, report, cases, user=False):
    controller = ROOT / 'conformance' / ('database_values_user_controller.py' if user else 'database_values_controller.py')
    tree = ast.parse(controller.read_bytes())
    assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == ('prelude' if user else 'code')
                           for target in node.targets)]
    assignment, = assignments
    if user:
        prefix = ast.literal_eval(assignment.value) + 'EXAMPLE=' + repr(EXAMPLE) + '\n'
        suffix = "\nDisplay('USER_DATABASE_PASSED')\n"
    else:
        prefix = ast.literal_eval(assignment.value.left.left)
        suffix = ast.literal_eval(assignment.value.right)
    with tarfile.open(path.parent / 'workspace.tar') as archive:
        members = {row.name.removeprefix('./'): row for row in archive.getmembers() if row.isfile()}
        read = lambda name: archive.extractfile(members[name]).read()
        assert json.loads(read('checks.json')) == report['checks']
        assert json.loads(read('runtime.json')) == report['runtime_sources']
        assert json.loads(read('cases.json')) == cases
        for name, spec in cases.items():
            row = report['checks'][name]
            assert row['passed'] and all(row[key] == value for key, value in spec.items()), name
            project = name.replace(':', '-')
            assert read(project + '/data/Procedures/main.py').decode('utf-8') == prefix + spec['source'] + suffix, name
            log = read(project + '/native.log')
            assert b'[ STATUS  ] FINISHED' in log and b'AddressSanitizer:' not in log and b'runtime error:' not in log, name
            assert (b'USER_DATABASE_PASSED' if user else b'CONFIGURED_DATABASE_PASSED') in log, name
        if user:
            assert json.loads(read('prompts.json')) == report['prompts']


def qualify(values_path, user_path, build_path):
    build = json.loads(build_path.read_bytes())
    assert build['passed'] and sha(Path(build['log']['path'])) == build['log']['sha256']
    values, user = (json.loads(path.read_bytes()) for path in (values_path, user_path))
    image = build['image']
    inputs = {}
    for path, report, cases in ((values_path, values, CASES), (user_path, user, USER_CASES)):
        validate_report(path, image, len(cases))
        assert set(report['checks']) == set(cases)
        runtime = report['runtime_sources']
        assert runtime['profile'] == 'fresh-wheel-plus-declared-diagnostic-overlay/1'
        assert runtime['integrated'] and runtime['overlay']
        verify_capture(runtime['integrated'], report['inputs'], report.get('lf_normalized_inputs'))
        assert set(runtime['overlay']['manifest']) == set(patch.PREIMAGES)
        for name in ('database_values_patches.py', 'database_values_provenance.py', 'database_values.Dockerfile'):
            source = ('source_port/' if name.endswith('_patches.py') else 'conformance/') + name
            assert runtime['overlay']['files'][name] == report['inputs'][source], name
        for name, digest in report['inputs'].items():
            assert name not in inputs or inputs[name] == digest, name
            inputs[name] = digest
        verify_archive(path, report, cases, report is user)
    assert values['runtime_sources'] == {key: value for key, value in user['runtime_sources'].items() if key != 'host_inputs'}
    assert user['runtime_sources']['host_inputs']['/opt/host/native.py'] == sha(ROOT / 'host_runtime/python/native.py')
    assert set(user['prompts']) == {'prompt-abort', 'prompt-rename'}
    for mode in ('abort', 'rename'):
        prompt = user['prompts']['prompt-' + mode]
        assert prompt['passed'] and prompt['mode'] == mode
        assert prompt['status'] == ('ABORTED' if mode == 'abort' else 'FINISHED')
        assert len(prompt['prompts']) == (1 if mode == 'abort' else 2)
        expected = {'existing.IMP': 'SAVED 42\n'}
        if mode == 'rename':
            expected['renamed.IMP'] = 'KEY\t7\n'
        assert prompt['files'] == expected
    name, = patch.PREIMAGES
    with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
        original = archive.read('src/spell/' + name)
    composed = original
    for recipe in (data_files_patches, database_import_patches, user_database_patches):
        if name in recipe.PREIMAGES:
            composed = recipe.apply(name, composed)
    assert hashlib.sha256(composed).hexdigest() == patch.PREIMAGES[name]
    patched = hashlib.sha256(patch.apply(name, composed)).hexdigest()
    runtime = values['runtime_sources']
    stage = runtime['overlay']['manifest'][name]
    assert stage == {'preimage_sha256': patch.PREIMAGES[name], 'sha256': patched}
    assert runtime['installed'][name] == patched
    assert runtime['integrated']['python_sources'][name] == patch.PREIMAGES[name]
    assert runtime['overlay']['files']['original/' + name] == patch.PREIMAGES[name]
    assert runtime['overlay']['files']['patched/' + name] == patched
    retained = {}
    for label in ('database_values_baseline', 'database_values_trace'):
        path = ROOT / 'conformance/evidence' / (label + '.json')
        record = json.loads(path.read_bytes())
        raw_path = Path(record['raw']['path'])
        assert not record['passed'] and sha(raw_path) == record['raw']['sha256']
        assert sha(raw_path.parent / 'workspace.tar') == record['raw']['workspace_sha256']
        raw = json.loads(raw_path.read_bytes())
        assert raw['runtime_image'] == build['base_image']
        assert {name for name, row in raw['checks'].items() if not row['passed']} == {'octal-values', 'octal-boundaries', 'import-recovery'}
        retained[label] = reference(path)
    for name in ('conformance/database_values_report.py', 'tests/test_database_values_report.py'):
        inputs[name] = sha(ROOT / name)
    return dict(passed=True, scope='Declared diagnostic overlay: corrected legacy octal values with existing importer/persistence regressions; no inventory promotion',
        runtime_image=image, base_image=build['base_image'], inputs=inputs, qualified_contracts=[],
        raw={label: {**reference(path), 'workspace_sha256': sha(path.parent / 'workspace.tar')}
             for label, path in (('values', values_path), ('user', user_path))},
        build=reference(build_path), passed_checks={'values_and_import': len(CASES), 'user_persistence': len(USER_CASES), 'user_prompts': 2},
        source={'name': 'spell/utils/vimport.py', 'preimage_sha256': patch.PREIMAGES['spell/utils/vimport.py'], 'patched_sha256': patched},
        retained_failures=retained,
        remaining=['Fresh composed native/driver wheels and image qualification', 'Full affected regression and inventory mapping'],
        full_v05_accepted=False, full_v06_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('values', 'user', 'build'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = qualify(args.values, args.user, args.build)
    output = ROOT / 'conformance/evidence/database_values.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': str(output), 'passed': True, 'checks': report['passed_checks']}))


if __name__ == '__main__':
    main()
