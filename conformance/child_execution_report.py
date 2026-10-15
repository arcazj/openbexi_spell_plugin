"""Map independently observed startup modes to the bounded p88 requirements."""
import argparse
import json
from pathlib import Path

from child_return_report import qualify as qualify_returns, sha, ROOT

CONTRACTS = ['CMP-LRM244-EXAMPLE-156', 'CMP-LRM244-EXAMPLE-158',
             'CMP-LRM244-SECTION-4-16-1-4-112']


def loads(automatic, blocking, recovery):
    return ('start', f'automatic-{automatic}-blocking-{blocking}-' + ('recovery' if recovery else 'failure'))


GROUPS = {
    CONTRACTS[0]: {
        'positive': [('modes', 'nonblocking-success')],
        'boundary': [('modes', 'nonblocking-late-error'), ('modes', 'manual-nonblocking')],
        'failure': [loads(True, False, False), loads(False, False, False)],
        'recovery': [loads(True, False, True), loads(False, False, True)],
    },
    CONTRACTS[1]: {
        'positive': [('modes', 'manual-blocking')],
        'boundary': [('modes', 'manual-nonblocking')],
        'failure': [loads(False, True, False), loads(False, False, False)],
        'recovery': [loads(False, True, True), loads(False, False, True)],
    },
    CONTRACTS[2]: {
        'positive': [('modes', 'blocking-success'), ('modes', 'manual-blocking')],
        'boundary': [('modes', 'blocking-immediate'), ('modes', 'manual-nonblocking')],
        'failure': [loads(a, b, False) for a in (True, False) for b in (True, False)],
        'recovery': [loads(a, b, True) for a in (True, False) for b in (True, False)],
    },
}


def qualify(start_path, modes_path, image):
    verified = qualify_returns(start_path, modes_path, image)
    raw = {name: json.loads(path.read_bytes()) for name, path in (('start', start_path), ('modes', modes_path))}
    # The shared verifier checks real child files, inventory and event identities,
    # three PAUSED samples before manual RUN, and parent timing during PROMPT.
    assert sha(ROOT / 'docs/reference/SPELL - Language Reference - 2.4.4.pdf') == 'ed13fae748997a48d6930ac40a30fb31f8b54119be0005a0431a1920613801c3'
    inventory = {row['id']: row for row in json.loads((ROOT / 'conformance/inventory.json').read_bytes())['rows']}
    for contract in CONTRACTS:
        assert inventory[contract]['pages'] == '88' and inventory[contract]['package'] == 'FLOW'
    checks = {}
    for contract, dimensions in GROUPS.items():
        for dimension, observations in dimensions.items():
            dependencies = []
            for kind, name in observations:
                key = kind + '/' + name + ':' + dimension
                dependencies.append(key)
                assert raw[kind]['checks'][name]['passed'] is True
                checks[key] = dict(passed=True, dimension=dimension, contracts=[],
                    raw_check={'report': kind, 'check': name},
                    oracle='Original native parent/child files, recorded PAUSED/PROMPT/terminal observations and context inventory agree with the source and expected result.')
            checks[contract + ':' + dimension] = dict(passed=True, dimension=dimension,
                contracts=[contract], dependencies=dependencies, legacy_spelling_supported=True,
                oracle='LRM p88: nonblocking returns after loading, including later child errors; automatic execution begins immediately, while manual execution waits for explicit RUN. Failed loads and successful subsequent starts are separately observed.')
    inputs = dict(verified['inputs'])
    for name in ('conformance/child_execution_report.py', 'conformance/CHILD_EXECUTION.md',
                 'tests/test_child_execution_report.py'):
        inputs[name] = sha(ROOT / name)
    return dict(passed=True, runtime_image=image, inputs=inputs, checks=checks,
        qualified_contracts=CONTRACTS, raw=verified['raw'], native_controls=17,
        scope='LRM p88 Examples 156/158 and Automatic/Manual section; explicit-import installed native profile.',
        exclusions=['Interactive failure policy and full Blocking section', 'Visible/Hidden GUI behavior',
                    'Global modifiers', 'Procedure-library priorities', 'Whole StartProc', 'Checkpoint recovery'],
        full_v05_accepted=False, full_v06_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=Path, required=True)
    parser.add_argument('--modes', type=Path, required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    report = qualify(args.start, args.modes, args.image)
    path = ROOT / 'conformance/evidence/child_execution.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': str(path), 'native_controls': 17, 'contracts': len(CONTRACTS)}))


if __name__ == '__main__':
    main()
