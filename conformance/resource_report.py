"""Qualify resource updates/reads and demonstrated GDB lookups on GENERIC GCS."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from resource_cases import CASES, METADATA

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = {'positive', 'boundary', 'failure', 'recovery'}
CONTRACTS = {'CMP-LRM244-' + name: package for name, package in (
    ('FUNCTION-GETRESOURCE', 'FILES'), ('FUNCTION-SETRESOURCE', 'FILES'),
    ('EXAMPLE-111', 'FILES'), ('EXAMPLE-112', 'FILES'), ('EXAMPLE-113', 'FILES'),
    ('EXAMPLE-140', 'DATA'), ('EXAMPLE-141', 'DATA'))}


def qualify(raw):
    report = deepcopy(raw)
    assert report['controller_exit_code'] == 0
    assert report['observations']['passed'] and report['observations']['status'] == 'FINISHED'
    assert set(report['checks']) == set(CASES)
    for name, row in report['checks'].items():
        assert row['passed'] and row['source'] == CASES[name], name
        assert row['contracts'] == METADATA[name]['contracts'], name
        assert row['dimension'] == METADATA[name]['dimension'], name
        assert len(row['prompts']) == len(row['expected_prompts']), name
        for prompt, plan in zip(row['prompts'], row['expected_prompts']):
            assert prompt['answer'] == plan['answer'], name
            assert set(prompt['choices']) == set(plan['choices']), name
    for path, expected in report['inputs'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
    assert report['runtime_sources']['installed']['/opt/host/native.py'] == report['inputs']['host_runtime/python/native.py']
    report['qualified_contracts'] = sorted({c for row in report['checks'].values() for c in row['contracts']})
    assert set(report['qualified_contracts']) == set(CONTRACTS)
    inventory = {row['id']: row for row in json.loads((ROOT / 'conformance/inventory.json').read_bytes())['rows']}
    for identifier, package in CONTRACTS.items():
        assert inventory[identifier]['package'] == package
        assert {r['dimension'] for r in report['checks'].values() if identifier in r['contracts']} == DIMENSIONS
    report['inputs']['conformance/resource_report.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['scope'] = {
        'manual': 'SPELL Language Reference 2.4.4 pp69/80: resource scope and parameters depend on the driver and GCS.',
        'profile': 'Existing shared GENERIC simulator resources with finite, non-null JSON values within the driver payload limit. IsLocal=True is unsupported; None retains the original unavailable sentinel. This does not claim arbitrary GCS or Python object support.',
        'read': 'Native GetResource preserves exact False, zero, empty string/list/dict, nested dictionaries, float and Unicode values. Missing resources and invalid arguments fail with catchable SPELL exceptions.',
        'write': 'Native SetResource updates existing resources through real binary RPC and the persistent ground database. Dictionary values, including keys named like modifiers, remain data. Rejected names, arity, unavailable/non-finite/oversize values and unsupported local scope do not change resource state or create effect journal rows.',
        'existence': 'The SPELL proxy checks existence before the update RPC. The lower administrative RPC retains resource creation. This profile has no delete API; atomicity against external direct database deletion is not claimed.',
        'gdb': 'Actual original runtime GDB contains explicit fixture mappings and drives native resource calls. Examples113/140/141 exercise name/value and calibration lookups with independent persistent-state assertions.',
        'open': 'Example139 and DATABASE-GDB remain open because configured nonempty database-file loading is not demonstrated here. This report does not qualify broad COMMON modifiers, local resources, GetResources, resource-status/link APIs, or desktop behavior.',
        'runtime': 'A development overlay binds original/ported/patched source and installed artifacts. Fresh wheel RECORD verification is a separate distribution gate.'
    }
    report['full_v05_accepted'] = report['v06_dependency_satisfied'] = False
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    args = parser.parse_args()
    raw = args.raw.read_bytes()
    report = qualify(json.loads(raw))
    report['raw_report_sha256'] = hashlib.sha256(raw).hexdigest()
    output = ROOT / 'conformance/evidence/resource.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(output), contracts=len(report['qualified_contracts']),
                         checks=len(report['checks']), sha256=hashlib.sha256(output.read_bytes()).hexdigest()), indent=2))


if __name__ == '__main__':
    main()
