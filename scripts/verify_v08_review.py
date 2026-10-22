"""Check source preservation, baseline evidence, installed bytes and review links."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import struct
import subprocess
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, timeout=30).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ide', required=True, type=Path)
    parser.add_argument('--original', required=True, type=Path)
    parser.add_argument('--installed-receipt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    docs = root / 'docs/v0.8'
    audit = json.loads((docs / 'evidence/baseline-audit.json').read_bytes())
    checks = []
    assert git(root, 'rev-parse', 'v0.7^{commit}') == audit['baseline']
    assert git(args.ide, 'rev-parse', 'HEAD') == audit['ide']['head']
    assert git(args.ide, 'status', '--short') == audit['ide']['status']
    assert git(args.original, 'status', '--short') == audit['original_worktree']['status']
    for name, digest in audit['original_worktree']['preserved_file_sha256'].items():
        assert sha(args.original / name) == digest, name
    checks.append('v0.7 tag, IDE source and four original dirty files preserved')
    changed = git(root, 'diff', '--name-only', audit['baseline'], 'HEAD').splitlines()
    changed += git(root, 'diff', '--name-only', 'HEAD').splitlines()
    assert all(name.startswith(('docs/v0.8/', 'scripts/audit_v08_', 'scripts/trace_v07_',
                                'scripts/render_v08_', 'scripts/verify_v08_')) for name in changed)
    checks.append('No production runtime source differs from v0.7')
    verified_reports = 0
    for repo, report in ((root, 'docs/V07_QUALIFICATION.json'),
                         (args.ide, 'docs/IDE_SPELL_V07_QUALIFICATION.json')):
        accepted = json.loads((repo / report).read_bytes())
        assert accepted['accepted'] and accepted['passed']
        for record in accepted['reports'].values():
            path = repo / record['path']
            assert sha(path) == record['sha256'], str(path)
            assert path.stat().st_size == record['bytes'], str(path)
            verified_reports += 1
    checks.append(f'{verified_reports} retained accepted evidence files match SHA-256 and size')
    totals = {}
    for name, expected in (('baseline-regressions.xml', 37), ('native.xml', 1)):
        suites = ET.parse(docs / 'evidence' / name).getroot().iter('testsuite')
        values = {k: 0 for k in ('tests', 'errors', 'failures', 'skipped')}
        for suite in suites:
            for key in values:
                values[key] += int(suite.get(key, 0))
        assert values == dict(tests=expected, errors=0, failures=0, skipped=0), values
        totals[name] = values
    trace = json.loads((docs / 'evidence/native-trace.json').read_bytes())
    receipt = json.loads(args.installed_receipt.read_bytes())
    assert trace['passed'] and all(trace['native_processes_seen'].values())
    assert trace['selected_test_sha256'] == receipt['copied_tests']['native_driver_acceptance.py']
    checks.append('38 fresh baseline tests passed; native process tree and accepted installed oracle verified')
    installed_count = 0
    for package in ('openbexi-ide', 'openbexi-spell-host', 'openbexi-spell-shared', 'openbexi-spell-dss'):
        expected = receipt['installed_wheels'][package]
        distribution = importlib.metadata.distribution(package)
        assert distribution.version == expected['version'] == trace['installed_versions'][package]
        for member, digest in expected['members'].items():
            assert sha(Path(distribution.locate_file(member))) == digest, package + ':' + member
            installed_count += 1
    checks.append(f'{installed_count} installed package members match the accepted v0.7 receipt')
    diagram = json.loads((docs / 'diagrams/manifest.json').read_bytes())
    assert diagram['repeatable'] and len(diagram['files']) == 10
    dimensions = {}
    for name, digest in diagram['files'].items():
        path = docs / 'diagrams' / name
        assert sha(path) == digest, name
        if name.endswith('.png'):
            raw = path.read_bytes()
            assert raw[:8] == b'\x89PNG\r\n\x1a\n'
            dimensions[name] = struct.unpack('>II', raw[16:24])
    for page in docs.glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)', page.read_text(encoding='utf-8')):
            if target.startswith(('https://', 'http://', '#')):
                continue
            assert (page.parent / target.split('#', 1)[0]).exists(), (page.name, target)
    checks.append('Diagram checksums, repeat rendering, PNG headers and local document links verified')
    status = json.loads((docs / 'STATUS.json').read_bytes())
    assert status['implementation_started'] is False and status['release_published'] is False
    checks.append('G1 remains pending; no implementation or publication mislabeled complete')
    result = dict(passed=True, checks=checks, tests=totals, png_dimensions=dimensions,
                  baseline=audit['baseline'], requirements_base=audit['requirements_commit'],
                  installed_members_verified=installed_count, retained_reports_verified=verified_reports,
                  harness_sha256=sha(Path(__file__)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
