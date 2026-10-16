"""Qualify blocking child states and failure policy from native observations."""
import argparse
import json
from pathlib import Path

from child_policy_cases import CASES
from child_return_report import qualify as qualify_returns, sha, ROOT
from installed_provenance import verify_capture
from run_language_regressions import validate_report

CONTRACTS = ['CMP-LRM244-CONSTANT-EXECUTION-STATE-' + state
             for state in ('ABORTED', 'ERROR', 'FINISHED')] + [
    'CMP-LRM244-MODIFIER-BLOCKING', 'CMP-LRM244-SECTION-4-16-1-2-110']


def verify_policy(path, image):
    raw = json.loads(path.read_bytes())
    validate_report(path, image, len(CASES))
    assert raw['passed'] and not raw['timed_out'] and set(raw['checks']) == set(CASES)
    runtime = raw['runtime_sources']['integrated']
    assert runtime is not None
    verify_capture(runtime, raw['inputs'])
    assert raw['host_inputs'] == {p.name: sha(p) for p in (ROOT / 'host_runtime/python').glob('*.py')}
    assert json.loads((path.parent / 'workspace/checks.json').read_bytes()) == raw['checks']
    for name, spec in CASES.items():
        row = raw['checks'][name]
        assert row['sources'] == {key: spec[key] for key in ('parent', 'child', 'good')}
        assert row['parent_status'] == spec['expected_parent']
        assert row['answers'] == [spec['action']] and len(row['prompts']) == 1
        action_names = {'A': 'ABORT', 'R': 'REPEAT', 'K': 'SKIP', 'Q': 'CANCEL'}
        assert [action_names.get(code, code) for code in row['prompts'][0]['ExpectedValues'].split('\x04')] == ['ABORT', 'REPEAT', 'SKIP', 'CANCEL']
        assert row['held'] == [dict(parent='PROMPT', child=spec['outcome'], attempts=1,
                                   parent_returned=False)] * 3
        assert row['attempts'] == spec['expected_attempts']
        assert not any(key.endswith('_error') for key in row)
        project = path.parent / 'workspace' / name
        for filename, key in (('main.py', 'parent'), ('child.py', 'child'), ('good.py', 'good')):
            assert (project / filename).read_text(encoding='utf-8') == spec[key]
        assert (project / 'attempts.txt').read_text() == str(spec['expected_attempts'])
        for filename, key in (('native.log', 'native_log_sha256'), ('events.json', 'events_sha256')):
            assert sha(project / filename) == row[key]
        log = (project / 'native.log').read_text(encoding='utf-8')
        assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
        events = json.loads((project / 'events.json').read_bytes())
        prompts = [event['message']['fields'] for event in events
                   if event.get('message', {}).get('id') == 'MSG_PROMPT']
        assert prompts == row['prompts']
        assert (project / 'child-completed.txt').exists() is (spec['action'] == 'REPEAT')
        if spec['action'] == 'ABORT':
            assert all(not (project / name).exists() for name in
                       ('first-return.json', 'parent-result.json', 'recovery-completed.txt'))
        else:
            assert row['result'] == dict(returned=spec['expected_return'], recovered=True)
            assert json.loads((project / 'parent-result.json').read_bytes()) == row['result']
            assert json.loads((project / 'first-return.json').read_bytes()) is spec['expected_return']
            assert (project / 'recovery-completed.txt').read_text() == 'finished'
    return raw


def qualify(policy_path, start_path, modes_path, image):
    prior = qualify_returns(start_path, modes_path, image)
    policy = verify_policy(policy_path, image)
    modes = json.loads(modes_path.read_bytes())
    assert policy['runtime_sources']['integrated'] == modes['runtime_sources']['integrated']
    inputs = dict(prior['inputs'])
    for name, digest in policy['inputs'].items():
        assert name not in inputs or inputs[name] == digest
        inputs[name] = digest
    for name in ('conformance/child_policy_report.py', 'conformance/CHILD_POLICY.md',
                 'tests/test_child_policy_report.py'):
        inputs[name] = sha(ROOT / name)
    checks = {}
    # Each selected observation retains a separate native oracle and source.
    # Error/abort must hold the parent at PROMPT without a repeat or return.
    for contract in CONTRACTS:
        state = contract.rsplit('-', 1)[-1]
        selected = [name for name in CASES if state not in ('ERROR', 'ABORTED')
                    or CASES[name]['outcome'] == state]
        groups = {
            'positive': [('policy', name) for name in selected if name.endswith('-cancel')],
            'boundary': [('policy', name) for name in selected if name.endswith('-skip')],
            'failure': [('policy', name) for name in selected if name.endswith('-abort')],
            'recovery': [('policy', name) for name in selected if name.endswith('-repeat')],
        }
        if state == 'FINISHED' or contract in CONTRACTS[-2:]:
            for dimension in groups:
                groups[dimension].append(('prior', 'return:' + dimension))
        if state == 'ERROR':
            groups['boundary'].append(('modes', 'nonblocking-late-error'))
        for dimension, observations in groups.items():
            dependencies = []
            for kind, name in observations:
                key = kind + '/' + name + ':' + dimension
                dependencies.append(key)
                source = {'prior': prior, 'modes': modes, 'policy': policy}[kind]
                assert source['checks'][name]['passed']
                checks[key] = dict(passed=True, dimension=dimension, contracts=[],
                    raw_check=dict(report=kind, check=name),
                    oracle='Actual terminal status, held parent, exact default prompt choices, child attempt count, return value and independent recovery file effects are all asserted.')
            checks[contract + ':' + dimension] = dict(passed=True, dimension=dimension,
                contracts=[contract], dependencies=dependencies,
                oracle='LRM p88: blocking waits for FINISHED/ERROR/ABORTED and prompts on child failure; nonblocking does not turn later child errors into parent failures. Repetition and subsequent starts require explicit observed actions.')
    inventory = {row['id']: row for row in json.loads((ROOT / 'conformance/inventory.json').read_bytes())['rows']}
    assert all(inventory[name]['package'] == 'FLOW' for name in CONTRACTS)
    return dict(passed=True, runtime_image=image, inputs=inputs, checks=checks,
        qualified_contracts=CONTRACTS, native_controls=25,
        raw={**prior['raw'], 'policy': {'path': str(policy_path.resolve()), 'sha256': sha(policy_path)}},
        scope='LRM p88 child terminal states, Blocking modifier and blocking/nonblocking section',
        exclusions=['Visible/Hidden graphical behavior', 'Procedure-library priorities',
                    'Whole StartProc and argument object families', 'Checkpoint recovery'],
        full_v05_accepted=False, full_v06_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('policy', 'start', 'modes'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    report = qualify(args.policy, args.start, args.modes, args.image)
    output = ROOT / 'conformance/evidence/child_policy.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(output), contracts=len(CONTRACTS), checks=report['native_controls'])))


if __name__ == '__main__':
    main()
