"""Qualify the p83 database octal literal only on the composed installed wheel."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

from database_values_cases import CASES
from database_values_report import verify_archive
from installed_provenance import verify_capture, verify_stages
from user_database_cases import CASES as USER_CASES

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
from run_language_regressions import validate_report

CONTRACT = 'CMP-LRM244-SYNTAX-INTEGER-OCTAL'
DONOR = 'a494986733ce6f4ceefda41684824f12bfbc5660'
FORMAT_DONOR = '3f361e3c547056cbed7aa7e7ea8071b4b690a970'
DIMENSIONS = {'positive': 'octal-values', 'boundary': 'octal-boundaries',
              'failure': 'non-octal-text', 'recovery': 'import-recovery'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(values_path, user_path, image):
    values, user = (json.loads(path.read_bytes()) for path in (values_path, user_path))
    inputs = {}
    for path, report, cases in ((values_path, values, CASES), (user_path, user, USER_CASES)):
        validate_report(path, image, len(cases))
        assert set(report['checks']) == set(cases)
        capture = report['runtime_sources']
        assert not capture.get('overlay') and not capture.get('manifest')
        runtime = capture['integrated']
        assert runtime is not None and runtime['driver_composition'] is not None
        verify_capture(runtime, report['inputs'], report.get('lf_normalized_inputs'))
        for kind, record in runtime['manifest']['composition'].items():
            verify_stages(kind, record)
        assert runtime == values['runtime_sources']['integrated']
        assert capture['installed']['spell/utils/vimport.py'] == runtime['python_sources']['spell/utils/vimport.py']
        for name, digest in report['inputs'].items():
            assert name not in inputs or inputs[name] == digest, name
            inputs[name] = digest
        verify_archive(path, report, cases, report is user)
    # The native assertions must have read the original octal text, not an
    # equivalent decimal fixture that would conceal the importer defect.
    with tarfile.open(values_path.parent / 'workspace.tar') as archive:
        members = {row.name.removeprefix('./'): row for row in archive.getmembers() if row.isfile()}
        read = lambda name: archive.extractfile(members[name]).read()
        for name, spec in CASES.items():
            project = name.replace(':', '-')
            for key, file in (('ground', 'GroundDB/GDB.DB'), ('spacecraft', 'SpacecraftDB/SCDB.DB')):
                assert read(project + '/data/' + file).decode('utf-8') == spec[key], name
        observed = json.loads(read('octal-values/data/Procedures/imported-values.json'))
        assert observed['OCTAL'] == {'type': 'int', 'repr': '29'}
        observed = json.loads(read('octal-boundaries/data/Procedures/imported-values.json'))
        for key, value in {'ZERO': 0, 'ZEROS': 0, 'MAX_DIGIT': 7, 'NEGATIVE': -29,
                           'POSITIVE': 29, 'LARGE': 1208925819614629174706176}.items():
            assert observed[key] == {'type': 'int', 'repr': str(value)}, key
    assert user['runtime_sources']['installed']['/opt/host/native.py'] == sha(ROOT / 'host_runtime/python/native.py')
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

    donor_path = 'conformance/evidence/database_values.json'
    donor_bytes = subprocess.check_output(['git', 'show', DONOR + ':' + donor_path], cwd=ROOT)
    donor = json.loads(donor_bytes)
    assert donor['passed'] and donor['qualified_contracts'] == []
    assert donor['passed_checks'] == {'values_and_import': 24, 'user_persistence': 20, 'user_prompts': 2}
    source = donor['source']
    runtime = values['runtime_sources']['integrated']
    composition = runtime['manifest']['composition']['python']
    recipe = 'database_values_patches.py'
    stage, = [row for row in composition['stages'] if row['recipe'] == recipe]
    assert stage['sources'] == {source['name']: {
        'before_sha256': source['preimage_sha256'], 'after_sha256': source['patched_sha256']}}
    assert composition['recipes'][recipe]['sha256'] == donor['inputs']['source_port/' + recipe]
    final_digest = source['patched_sha256']
    format_donor = None
    if 'database_format_patches.py' in composition['recipes']:
        # The independently reviewed format extension follows the original octal
        # repair. Keep both exact stages and the final installed bytes bound.
        proof_bytes = subprocess.check_output(['git','show',FORMAT_DONOR+
            ':conformance/evidence/database_format_review.json'],cwd=ROOT)
        proof = json.loads(proof_bytes)
        original_path = Path(proof['raw']['formats']['path'])
        assert sha(original_path) == proof['raw']['formats']['sha256']
        original = json.loads(original_path.read_bytes())
        expected = original['runtime_sources']['overlay']['manifest'][source['name']]
        following = [row for row in composition['stages'] if source['name'] in row['sources']]
        assert following[-2]['recipe'] == recipe and following[-1]['recipe'] == 'database_format_patches.py'
        assert expected['preimage_sha256'] == final_digest
        assert following[-1]['sources'][source['name']] == {
            'before_sha256':final_digest,'after_sha256':expected['sha256']}
        assert composition['recipes']['database_format_patches.py']['sha256'] == original['inputs']['source_port/database_format_patches.py']
        final_digest = expected['sha256']
        format_donor = dict(commit=FORMAT_DONOR,sha256=hashlib.sha256(proof_bytes).hexdigest(),
            raw=proof['raw']['formats'],source=expected)
    assert composition['sources'][source['name']]['patched_sha256'] == final_digest
    assert runtime['python_sources'][source['name']] == final_digest
    inventory = json.loads((ROOT / 'conformance/inventory.json').read_bytes())
    item, = [row for row in inventory['rows'] if row['id'] == CONTRACT]
    assert item['name'] == '035' and item['pages'] == '83' and item['package'] == 'PY'
    assert sha(ROOT / 'docs/reference/SPELL - Language Reference - 2.4.4.pdf') == 'ed13fae748997a48d6930ac40a30fb31f8b54119be0005a0431a1920613801c3'
    checks = {}
    for dimension, name in DIMENSIONS.items():
        row = deepcopy(values['checks'][name])
        row.update(contracts=[CONTRACT], dimension=dimension, legacy_spelling_supported=True,
            oracle='LRM p83 database-file value grammar: literal 035 is integer 29; signed/zero/large octal, quoted and invalid-digit text, and import after an error have independent native assertions.')
        checks[name] = row
    for name in ('conformance/database_values_composed_report.py', 'conformance/database_values_report.py',
                 'conformance/database_values_user_controller.py', 'tests/test_database_values_composed_report.py'):
        inputs[name] = sha(ROOT / name)
    return dict(passed=True, runtime_image=image, inputs=inputs, checks=checks,
        qualified_contracts=[CONTRACT], source=source, stage=stage, format_donor=format_donor,
        diagnostic_donor={'commit': DONOR, 'path': donor_path, 'sha256': hashlib.sha256(donor_bytes).hexdigest()},
        raw={name: {'path': str(path.resolve()), 'sha256': sha(path),
                    'workspace_sha256': sha(path.parent / 'workspace.tar')}
             for name, path in (('values', values_path), ('user', user_path))},
        regressions={'values_and_import': len(CASES), 'user_persistence': len(USER_CASES), 'user_prompts': 2},
        scope='Original p83 database-file octal grammar on a freshly composed installed wheel; explicit-import native profile.',
        exclusions=['Python procedure-source octal literals', 'Complete database-file grammar', 'Whole database chapter'],
        full_v05_accepted=False, full_v06_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--values', type=Path, required=True)
    parser.add_argument('--user', type=Path, required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    report = qualify(args.values, args.user, args.image)
    output = ROOT / 'conformance/evidence/database_values_composed.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': str(output), 'contracts': 1, 'checks': report['regressions']}))


if __name__ == '__main__':
    main()
