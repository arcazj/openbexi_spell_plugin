"""Run all 122 Python inventory contracts in the exact original native image."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from installed_provenance import capture_client, input_paths

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qualify_host_adapter as host


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='openbexi-spell-host:v05-common')
    parser.add_argument('--output', type=Path, default=ROOT / '.qualification/v0.5/python')
    args = parser.parse_args()
    output = args.output.resolve() / uuid.uuid4().hex
    project = output / 'project'
    project.mkdir(parents=True)
    names = (
        'conformance/python_contracts.py', 'conformance/python_fixture.py',
        'conformance/run_python.py', 'conformance/python.md',
        'conformance/inventory.json', 'scripts/qualify_host_adapter.py',
        'docs/reference/SPELL - Language Reference - 2.4.4.pdf',
    )
    names = tuple(dict.fromkeys((*names, *input_paths(ROOT))))
    inputs = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}
    shutil.copyfile(ROOT/'conformance/installed_provenance.py',project/'installed_provenance.py')
    for name in ('python_contracts.py', 'python_fixture.py'):
        shutil.copyfile(ROOT / 'conformance' / name, project / name)
    (project / 'main.py').write_text(
        "import spell.lib\nfrom spell.lang.functions import Display\n"
        "Display('PYTHON_CONFORMANCE_BEGIN')\nimport python_contracts\n"
        "Display('PYTHON_CONFORMANCE_END')\n", encoding='utf-8')
    image = subprocess.check_output(
        ['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).strip()
    host.IMAGE, host.EVIDENCE = image, output
    client = host.Client(project)
    try:
        client.launch('main.py', noDebug=True)
        integrated = capture_client(client, inputs)
        client.request('configurationDone')
        assert client.event('exited', timeout=180)['exitCode'] == 0, 'Harness failed; inspect native transcript'
        client.event('terminated')
        report = json.loads(client.read_file('python-results.json'))
        report['runtime_image'] = image
        report['runtime_sources'] = {'integrated':integrated}
        assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
                   for name, digest in inputs.items()), 'Inputs changed during execution'
        report['inputs'] = inputs
        inventory = json.loads((ROOT / 'conformance/inventory.json').read_text(encoding='utf-8'))
        expected = {row['id'] for row in inventory['rows'] if row['package'] == 'PY'}
        actual = {name for check in report['checks'].values() for name in check['contracts']}
        assert len(expected) == 122 and actual == expected, (expected - actual, actual - expected)
        for identifier in expected:
            assert {check['dimension'] for check in report['checks'].values()
                    if identifier in check['contracts']} == {'positive', 'boundary', 'failure', 'recovery'}
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        failures = {name: row.get('error', 'Contained contract failed')
                    for name, row in report['checks'].items() if not row['passed']}
        print(json.dumps({'evidence': str(output), 'contracts': len(actual),
                          'checks': len(report['checks']), 'failures': failures,
                          'legacy_unsupported': sorted(report['legacy_contracts'])}, indent=2))
        return bool(failures)
    finally:
        client.close('python-contracts')


if __name__ == '__main__':
    raise SystemExit(main())
