"""Bind the named runtime SCDB read-only contract to actual native evidence."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from check import DIMENSIONS, supported_check
from scdb_cases import CASES, ROWS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source_port'))
import scdb_patches as patch


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path, report):
    return dict(path=str(path.resolve()), sha256=digest(path),
                runtime_image=report['runtime_image'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--database-import', required=True, type=Path)
    parser.add_argument('--checkpoint-gap', required=True, type=Path)
    parser.add_argument('--policy-oracle-correction', required=True, type=Path)
    args = parser.parse_args()
    report = deepcopy(json.loads(args.raw.read_bytes()))
    checkpoints = {'checkpoint:on_line', 'checkpoint:on_step'}
    assert report['controller_exit_code'] == 0
    assert set(report['checks']) == set(CASES) | checkpoints
    assert all(row['passed'] for row in report['checks'].values())
    for name, spec in CASES.items():
        assert all(report['checks'][name][key] == value for key, value in spec.items()), name
    for name in checkpoints:
        result = report['checks'][name]['result']
        assert result['restored'] and result['shared_saved_alias']
        assert result['alias_is_new_runtime_binding'] and result['readonly_type'] == 'ReadOnlyDatabase'
    for name, expected in report['inputs'].items():
        assert digest(ROOT/name) == expected, name
    runtime = report['runtime_sources']['scdb']
    assert runtime['archive_sha256'] == patch.ARCHIVE_SHA256
    assert runtime['recipe_sha256'] == digest(ROOT/'source_port/scdb_patches.py')
    with zipfile.ZipFile(ROOT/'docs/reference/SPELL2.6.10-src.zip') as archive:
        for name, preimage in patch.PREIMAGES.items():
            original = archive.read('src/spell/'+name)
            assert hashlib.sha256(original).hexdigest() == preimage
            patched = hashlib.sha256(patch.apply(name, original)).hexdigest()
            assert runtime['sources'][name] == dict(original_sha256=preimage,
                ported_sha256=preimage, patched_sha256=patched)
    baseline = json.loads(args.baseline.read_bytes())
    assert set(baseline['checks']) == set(CASES)
    assert baseline['runtime_sources']['scdb'] is None
    assert all(all(baseline['checks'][name][key] == value for key, value in spec.items())
               for name, spec in CASES.items())
    assert not baseline['checks']['write:assignment-existing']['passed']
    assert not baseline['checks']['read:detached-item']['passed']
    report['baseline'] = reference(args.baseline, baseline)
    report['baseline']['failed'] = [name for name, row in baseline['checks'].items() if not row['passed']]
    regression = json.loads(args.database_import.read_bytes())
    assert regression['runtime_image'] == report['runtime_image']
    assert len(regression['checks']) == 16 and all(row['passed'] for row in regression['checks'].values())
    report['regressions'] = {'database_import': dict(reference(args.database_import, regression), checks=16)}
    gap = json.loads(args.checkpoint_gap.read_bytes())
    assert gap['runtime_image'] == report['runtime_image']
    assert all(gap['checks'][name]['passed'] for name in CASES)
    for name in checkpoints:
        row = gap['checks'][name]
        assert not row['passed']
        assert 'checkpoint requires a synchronous thread-owned frame' in row['timeout_stdout'] + row['timeout_stderr']
    correction = json.loads(args.policy_oracle_correction.read_bytes())
    assert not correction['checks']['write:save-policy']['passed']
    report['retained_observations'] = {
        'checkpoint_lambda_error': dict(reference(args.checkpoint_gap, gap),
            status='unresolved', modes=['ON_LINE', 'ON_STEP'],
            observation='SCDB aliases and detached data restored, but rejecting writes through procedure-local lambdas after resume produced checkpoint requires a synchronous thread-owned frame and timed out. Direct public-method calls and direct SaveDictionary pass on identical runtime bytes. No original-error control has isolated the cause; generic lambda/error-handler checkpoint compatibility is not qualified.'),
        'save_failure_policy_oracle': dict(reference(args.policy_oracle_correction, correction),
            status='oracle-corrected',
            observation='The initial oracle used PromptUser=False for a SaveDictionary operation exception. The original helper uses PromptFailure for that policy, so the corrected actual native test uses PromptFailure=False with OnFailure=CANCEL. The original prompt/failure trace is retained; no runtime source change was made for this test correction.')}
    inventory = {row['id']: row for row in json.loads((ROOT/'conformance/inventory.json').read_bytes())['rows']}
    assert len(ROWS) == 2 and all(inventory[row]['package'] == 'DATA' for row in ROWS)
    report['qualified_contracts'] = ROWS
    report['contract_evidence'] = {}
    for dimension in DIMENSIONS:
        children = [name for name, spec in CASES.items() if spec['dimension'] == dimension]
        if dimension == 'recovery':
            children += sorted(checkpoints)
        assert children
        name = 'SCDB:'+dimension
        report['checks'][name] = dict(passed=True, dimension=dimension, contracts=ROWS,
            dependencies=children,
            oracle='Named runtime SCDB read-only policy and original backend compatibility are demonstrated by the referenced independent native '+dimension+' scenarios.')
        assert supported_check(report, name, dimension)
        report['contract_evidence'][dimension] = name
    report['inputs']['conformance/scdb_report.py'] = digest(Path(__file__))
    report['raw_report'] = dict(reference(args.raw, report),
        native_logs_archive_sha256=digest(args.raw.parent/'workspace.tar'), checks=26)
    report['scope'] = {
        'manual': 'LRM2.4.4 pp78-79: configured spacecraft database automatically loaded at procedure startup and exposed as the read-only SCDB object.',
        'initialization': 'Actual original native DBMGR startup selects the view by the configured SCDB name. Procedures verify initialization before explicit imports from spell.runtime. No Python builtins injection is claimed.',
        'backend': 'Configured original flat-file DatabaseFile backend, including real typed data, failed refresh snapshot preservation, and successful refresh recovery. Other backend profiles are not inferred.',
        'read_only': 'Public assignment, deletion, set, create, commit, SaveDictionary and DBMGR create fail without changing in-memory or independently observed file data. Nested get/item values and keys are detached. Original GDB and user databases remain writable and are independently reopened in fresh native processes.',
        'permissions': 'The contract protects the named runtime SCDB API. Direct filesystem writes, alternate file aliases, deliberate private-attribute manipulation and operating-system permissions are outside this claim.',
        'checkpoint': 'Both actual native ON_LINE and ON_STEP kill/resume modes restore saved aliases to the new runtime SCDB binding, preserve detached nested values and reject direct public method/SaveDictionary calls. The retained post-resume lambda/error-handler failure remains unresolved and is not included in acceptance.',
        'distribution': 'Diagnostic overlay over an audited integrated image with original/ported/patched sources and native identities retained. Overlay edits intentionally do not update installed wheel RECORD; a fresh composed wheel and installed RECORD audit are still required for distribution acceptance.'}
    report['full_v05_accepted'] = report['full_v06_accepted'] = report['v06_dependency_satisfied'] = False
    output = ROOT/'conformance/evidence/scdb.json'
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(output), contracts=ROWS, native_checks=26,
                         regression_checks=16, sha256=digest(output)), indent=2))


if __name__ == '__main__':
    main()
