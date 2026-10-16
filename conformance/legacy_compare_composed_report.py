"""Qualify only native procedure <> syntax on a freshly composed installed wheel."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from installed_provenance import verify_capture, verify_stages
from legacy_compare_report import verify_archive
from legacy_compare_cases import CASES, INVALID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
from run_language_regressions import validate_report

DONOR = 'fc44409cd5493ca0ad6e924b2b45d01d34387b6d'
CONTRACT = 'CMP-LRM244-OPERATOR-PYTHON-LEGACY-NOT-EQUAL'
DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(path, image):
    raw = json.loads(path.read_bytes())
    validate_report(path, image, len(CASES) + len(INVALID))
    verify_archive(path, raw, False)
    captured = raw['runtime_sources']
    assert captured['overlay'] is None
    runtime = captured['integrated']
    assert runtime is not None and runtime['driver_composition'] is not None
    verify_capture(runtime, raw['inputs'])
    for kind, record in runtime['manifest']['composition'].items():
        verify_stages(kind, record)
    for name, digest in runtime['native_artifacts'].items():
        assert captured['installed']['spell_native/bin/' + name] == digest
    for name, digest in runtime['python_sources'].items():
        assert captured['installed'][name] == digest
    donor_path = 'conformance/evidence/legacy_compare.json'
    encoded = subprocess.check_output(['git', 'show', DONOR + ':' + donor_path], cwd=ROOT)
    donor = json.loads(encoded)
    assert donor['passed'] and donor['qualified_contracts'] == [] and donor['passed_checks'] == 15
    native = runtime['manifest']['composition']['native']
    stages = [row for row in native['stages'] if row['recipe'] == 'legacy_compare_patches.py']
    changed = {name: row for stage in stages for name, row in stage['sources'].items()}
    assert len(stages) == 2 and set(changed) == set(donor['sources'])
    for name, row in donor['sources'].items():
        assert changed[name] == dict(before_sha256=row['ported_sha256'], after_sha256=row['patched_sha256'])
        assert native['sources'][name]['original_sha256'] == row['original_sha256']
        assert native['sources'][name]['patched_sha256'] == row['patched_sha256']
    for recipe in ('legacy_compare_patches.py', 'legacy_compare_syntax.py'):
        assert native['recipes'][recipe]['sha256'] == donor['recipes'][recipe]
    item, = [row for row in json.loads((ROOT / 'conformance/inventory.json').read_bytes())['rows']
             if row['id'] == CONTRACT]
    assert item['name'] == '<>' and item['pages'] == '21' and item['package'] == 'PY'
    assert sha(ROOT / 'docs/reference/SPELL - Language Reference - 2.4.4.pdf') == 'ed13fae748997a48d6930ac40a30fb31f8b54119be0005a0431a1920613801c3'
    checks = {}
    for dimension in DIMENSIONS:
        row = deepcopy(raw['checks'][dimension])
        row.update(contracts=[CONTRACT], dimension=dimension, legacy_spelling_supported=True,
            oracle='LRM p21 legacy <> in native procedure source: unequal/equal values, boundaries, raised __ne__ errors and subsequent successful comparisons; source and native terminal observations retained.')
        checks[dimension] = row
    inputs = dict(raw['inputs'])
    for name in ('conformance/legacy_compare_composed_report.py', 'conformance/legacy_compare_report.py',
                 'tests/test_legacy_compare_composed_report.py'):
        inputs[name] = sha(ROOT / name)
    return dict(passed=True, runtime_image=image, inputs=inputs, checks=checks,
        qualified_contracts=[CONTRACT], native_stages=stages,
        diagnostic_donor=dict(commit=DONOR, path=donor_path, sha256=hashlib.sha256(encoded).hexdigest()),
        raw=dict(path=str(path.resolve()), sha256=sha(path), workspace_sha256=sha(path.parent / 'workspace.tar')),
        regressions=len(raw['checks']), scope='Legacy <> compatibility in the native procedure compiler and AST analyzer',
        exclusions=['Imported Python modules', 'Python builtins eval and compile', 'Parent Python language sections'],
        full_v05_accepted=False, full_v06_accepted=False, stable_v1_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    report = qualify(args.raw, args.image)
    output = ROOT / 'conformance/evidence/legacy_compare_composed.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(output), contracts=1, checks=report['regressions'])))


if __name__ == '__main__':
    main()
