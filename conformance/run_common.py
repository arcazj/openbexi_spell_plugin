"""Qualify common language policies with an external native DAP controller."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qualify_host_adapter as host

# Native client protocol option codes, distinct from procedure bitmask constants.
ACTION_NAMES = dict(A='ABORT', R='REPEAT', S='RESEND', C='RECHECK', K='SKIP',
                    N='NOACTION', Q='CANCEL', H='HANDLE')


def terminal_checks(output):
    observations = {}
    for scenario in ('failure-auto', 'true-auto', 'false-auto', 'failure-interactive', 'uncaught', 'recovery'):
        project = output/scenario
        project.mkdir()
        # Abort must run in traced procedure code, not an imported oracle module.
        shutil.copyfile(ROOT/'conformance/common_edges.py', project/'main.py')
        client = host.Client(project)
        try:
            client.launch('main.py', spellArguments={'scenario':scenario})
            client.request('configurationDone')
            prompts = []
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                message = client.events.popleft() if client.events else client.next(deadline-time.monotonic())
                if message.get('event') == 'openbexi/inputRequest':
                    body = message['body']
                    prompts.append(body)
                    assert scenario == 'failure-interactive' and body['choices'] == 'A\x04K', body
                    client.request('openbexi/input', text='0')
                elif message.get('event') == 'exited':
                    code = message['body']['exitCode']
                    break
            else:
                raise TimeoutError(scenario)
            assert code == (0 if scenario == 'recovery' else 1), (scenario, code)
            assert len(prompts) == (1 if scenario == 'failure-interactive' else 0)
            assert client.read_file('cleanup.txt') == scenario
            if scenario == 'recovery':
                assert client.read_file('continued.txt') == 'completed'
                assert 'fresh native executor' in client.read_file('recovered.txt')
            else:
                try:
                    client.read_file('continued.txt')
                except subprocess.CalledProcessError:
                    pass
                else:
                    raise AssertionError('Native execution continued after abort/error')
            observations[scenario] = dict(exit_code=code, cleanup=True, prompts=prompts,
                fresh_defaults=True, continued=scenario == 'recovery')
        finally:
            client.close('common-' + scenario)
    checks = {}
    for dimension, scenarios in (
        ('positive', ['failure-auto']), ('boundary', ['true-auto', 'false-auto']),
        ('failure', ['failure-interactive', 'uncaught']), ('recovery', ['recovery']),
    ):
        checks['terminal-policy:' + dimension] = dict(dimension=dimension, passed=True,
            contracts=['CMP-LRM244-CONSTANT-ACTION-ABORT', 'CMP-LRM244-EXAMPLE-022'],
            oracle='LRM pp.28,31,116-117: abort/error prevents continuation, runs cleanup; only an explicit fresh executor recovers with original procedure defaults',
            observations={name: observations[name] for name in scenarios})
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='openbexi-spell-host:v05-time')
    parser.add_argument('--output', type=Path, default=ROOT / '.qualification/v0.5/common')
    args = parser.parse_args()
    output = args.output.resolve() / uuid.uuid4().hex
    project = output / 'project'
    project.mkdir(parents=True)
    inputs = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
        'conformance/common_contracts.py', 'conformance/common_edges.py', 'conformance/run_common.py',
        'conformance/build_common_patch.py', 'conformance/common.Dockerfile',
        'scripts/qualify_host_adapter.py',
        'conformance/inventory.json', 'source_port/patches.py',
        'docs/reference/SPELL - Language Reference - 2.4.4.pdf')}
    shutil.copyfile(ROOT/'conformance/common_contracts.py', project/'common_contracts.py')
    (project/'main.py').write_text('import common_contracts\n', encoding='utf-8')
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image,
                                    '--format', '{{.Id}}'], text=True).strip()
    host.IMAGE, host.EVIDENCE = image, output
    client = host.Client(project)
    observed = defaultdict(list)
    try:
        client.launch('main.py')
        client.request('configurationDone')
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            message = client.events.popleft() if client.events else client.next(deadline-time.monotonic())
            event, body = message.get('event'), message.get('body', {})
            if event == 'exited':
                assert body['exitCode'] == 0, 'Common harness failed; inspect transcript'
                break
            if event != 'openbexi/inputRequest':
                continue
            active = json.loads(client.read_file('common-active.json'))
            check = active['check']
            index = len(observed[check])
            expected = active['prompts'][index] if index < len(active['prompts']) else None
            choices = [ACTION_NAMES.get(code, code) for code in body['choices'].split('\x04')]
            row = {'choices': choices, 'text': body['text'], 'expected': expected}
            observed[check].append(row)
            if expected and expected.get('repair'):
                relative = expected['repair']
                assert Path(relative).name == relative and relative.startswith('common-repair-')
                subprocess.run(['docker', 'exec', client.name, 'python', '-c',
                    'from pathlib import Path; import sys; Path(sys.argv[1]).write_text("repaired by controller")',
                    '/workspace/' + relative], check=True, capture_output=True, timeout=10)
            answer = expected['answer'] if expected else 'SKIP'
            assert answer in choices, ('No safe test answer', check, choices, answer)
            client.request('openbexi/input', text=str(choices.index(answer)))
        else:
            raise TimeoutError('Common conformance did not exit')
        report = json.loads(client.read_file('common-results.json'))
        for identifier, row in report['checks'].items():
            prompts = observed.get(identifier, [])
            expected = row.pop('expected_prompts')
            matched = len(prompts) == len(expected) and all(
                prompt['choices'] == want['choices'] for prompt, want in zip(prompts, expected))
            row['controller_prompts'] = prompts
            if not matched:
                row['passed'] = False
                row['controller_error'] = {'expected': expected, 'observed': prompts}
        client.close('common-contracts')
        client = None
        report['checks'].update(terminal_checks(output))
        report['runtime_image'] = image
        assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest
                   for name, digest in inputs.items()), 'Inputs changed while running'
        report['inputs'] = inputs
        inventory = json.loads((ROOT/'conformance/inventory.json').read_text(encoding='utf-8'))
        allowed = {row['id'] for row in inventory['rows'] if row['package'] == 'COMMON'}
        actual = {name for row in report['checks'].values() for name in row['contracts']}
        assert actual <= allowed, actual - allowed
        (output/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
        failures = {name: row.get('error', row.get('controller_error'))
                    for name, row in report['checks'].items() if not row['passed']}
        print(json.dumps({'evidence': str(output), 'checks': len(report['checks']),
                          'contracts': len(actual), 'failures': failures}, indent=2))
        return bool(failures)
    finally:
        if client is not None:
            client.close('common-contracts')


if __name__ == '__main__':
    raise SystemExit(main())
