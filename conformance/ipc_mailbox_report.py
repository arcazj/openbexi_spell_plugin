"""Retain differential race evidence and real IPC regression results."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source_port'))
from ipc_mailbox_patches import SOURCE, PREIMAGE, apply
from ipc_mailbox_provenance import qualification_identity
from checkpoint_identity_run import checks_passed
from checkpoint_identity_report import ERRORS, RECOVERY, MODES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path):
    return {'path': str(path.resolve()), 'sha256': sha(path)}


def validate_probes(directory):
    manifest = json.loads((directory / 'manifest.json').read_bytes())
    original = (directory / 'original/source.C').read_bytes()
    patched = (directory / 'patched/source.C').read_bytes()
    assert manifest['passed'] is True and manifest['source'] == SOURCE
    assert sha(directory / 'original/source.C') == manifest['preimage_sha256'] == PREIMAGE
    assert sha(directory / 'patched/source.C') == manifest['patched_sha256']
    assert patched == apply(original)
    for label in ('original', 'patched'):
        for operation in ('place', 'cancel'):
            probe = manifest['probes'][label + '-' + operation]
            log = directory / label / (operation + '.log')
            assert sha(log) == probe['log_sha256']
            content = log.read_bytes()
            if label == 'original':
                assert probe['exit_code'] != 0
                assert b'AddressSanitizer: heap-use-after-free' in content
            else:
                assert probe['exit_code'] == 0 and b'PASS' in content
                assert b'AddressSanitizer:' not in content and b'runtime error:' not in content
    for name, expected in manifest['artifacts'].items():
        assert sha(directory / 'compiled' / name) == expected
    for name, expected in manifest['recipes'].items():
        assert sha(directory / 'recipes' / name) == expected
    return manifest


def validate_runtime(path, image, cases, kind):
    report = json.loads(path.read_bytes())
    assert report['runtime_image'] == image and report['passed'] is True
    assert report['controller_exit_code'] == 0
    assert report['options'] == dict(cases=list(cases), modes=list(MODES), kind=kind)
    assert checks_passed(report['checks'], report['options'])
    for name, expected in report['inputs'].items():
        assert sha(ROOT / name) == expected, name
    identity = qualification_identity(report['runtime_sources'], report['inputs'],
                                      report.get('lf_normalized_inputs'))
    return report, identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--errors', required=True, type=Path)
    parser.add_argument('--recovery', required=True, type=Path)
    parser.add_argument('--retained-failure', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'conformance/evidence/ipc_mailbox.json')
    args = parser.parse_args()
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image,
                                     '--format', '{{.Id}}'], text=True).strip()
    errors, identity = validate_runtime(args.errors, image, ERRORS, 'error-ipc')
    recovery, other = validate_runtime(args.recovery, image, RECOVERY, 'recovery')
    assert identity == other
    failed = json.loads(args.retained_failure.read_bytes())
    assert failed['passed'] is False and any(row.get('sanitizer_failure') for row in failed['checks'].values())
    name = 'openbexi-mailbox-evidence-' + uuid.uuid4().hex
    folder = ROOT / '.qualification/ipc-mailbox' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    try:
        subprocess.run(['docker', 'create', '--name', name, '--network=none', '--entrypoint', 'true', image],
                       check=True, capture_output=True)
        subprocess.run(['docker', 'cp', name + ':/opt/ipc-mailbox-patch/.', str(folder)],
                       check=True, capture_output=True)
    finally:
        subprocess.run(['docker', 'rm', name], check=True, capture_output=True)
    manifest = validate_probes(folder)
    assert manifest == identity['evidence']
    base = json.loads((folder / 'baseline-installed.json').read_bytes())
    assert base == errors['runtime_sources']['baseline'] == recovery['runtime_sources']['baseline']
    result = dict(schema='openbexi.spell.ipc-mailbox/1', passed=True, runtime_image=image,
        source=SOURCE, preimage_sha256=PREIMAGE, patched_sha256=manifest['patched_sha256'],
        diagnostic_manifest=reference(folder / 'manifest.json'),
        retained_failure=reference(args.retained_failure), native_artifacts=manifest['artifacts'],
        probes={name: dict(row, log=reference(folder / name.split('-')[0] / (name.split('-')[1] + '.log')))
                for name, row in manifest['probes'].items()},
        error_controls={'checks': len(errors['checks']), 'raw': reference(args.errors)},
        recovery_controls={'checks': len(recovery['checks']), 'raw': reference(args.recovery)},
        recipes=manifest['recipes'],
        scope=['Producer and cancellation retain the queue until publication returns',
               'A queued response wins over duplicates and cancellation',
               'Late responses are rejected after removal',
               'Original native error and checkpoint recovery controls pass'],
        limitations=['Diagnostic overlay; fresh composed wheels and complete regressions remain required'],
        full_v05_accepted=False, full_v06_accepted=False, stable_v1_accepted=False)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(args.output), passed=True, errors=len(errors['checks']),
                          recovery=len(recovery['checks']))))


if __name__ == '__main__':
    main()
