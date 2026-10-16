"""Bind startup observations to the listener correction in an installed wheel."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from context_snapshot_report import verify_archive
from checkpoint_identity_provenance import qualification_identity
from installed_provenance import verify_capture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
from run_language_regressions import validate_report

DONOR = '342b1f12ad6c315a686581b64455c250c8d1d08b'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(path, image):
    raw = json.loads(path.read_bytes())
    validate_report(path, image, 40)
    assert raw['passed'] and len(raw['checks']) == 40
    capture = raw['runtime_sources']
    assert 'context_snapshot_overlay' not in capture
    verify_capture(capture, raw['inputs'])
    qualification_identity(capture, raw['inputs'])
    verify_archive(path, raw, 'startup')
    donor_path = 'conformance/evidence/context_snapshot.json'
    encoded = subprocess.check_output(['git', 'show', DONOR + ':' + donor_path], cwd=ROOT)
    donor = json.loads(encoded)
    assert donor['passed'] and donor['passed_checks'] == {'errors':8, 'recovery':22, 'startup':40}
    native = capture['manifest']['composition']['native']
    recipe = 'context_snapshot_patches.py'
    stage, = [row for row in native['stages'] if row['recipe'] == recipe]
    assert stage['sources'] == {donor['source']: {
        'before_sha256': donor['preimage_sha256'], 'after_sha256': donor['patched_sha256']}}
    assert native['sources'][donor['source']] == dict(original_sha256=donor['original_sha256'],
        ported_sha256=donor['preimage_sha256'], patched_sha256=donor['patched_sha256'])
    assert native['recipes'][recipe]['sha256'] == donor['recipes'][recipe]
    inputs = dict(raw['inputs'])
    for name in ('conformance/context_snapshot_composed_report.py',
                 'conformance/context_snapshot_report.py', 'tests/test_context_snapshot_composed_report.py'):
        inputs[name] = sha(ROOT / name)
    return dict(passed=True, runtime_image=image, inputs=inputs, checks=raw['checks'],
        qualified_contracts=[], native_stage=stage, native_source=native['sources'][donor['source']],
        diagnostic_donor=dict(commit=DONOR, path=donor_path, sha256=hashlib.sha256(encoded).hexdigest()),
        raw=dict(path=str(path.resolve()), sha256=sha(path), workspace_sha256=sha(path.parent / 'workspace.tar')),
        scope='Forty actual startup/discovery/run/cleanup cycles using the composed listener state mutex',
        limitations=['The controlled diagnostic proves the race; repeated startup alone is not a race proof',
            'No new language inventory row is inferred from this infrastructure correction'],
        full_v05_accepted=False, full_v06_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    report = qualify(args.raw, args.image)
    output = ROOT / 'conformance/evidence/context_snapshot_composed.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(output), passed=True, checks=len(report['checks']))))


if __name__ == '__main__':
    main()
