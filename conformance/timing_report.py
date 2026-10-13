"""Qualify only complete Wait modifier behavior from actual native evidence."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from installed_provenance import verify_capture
from timing_cases import CASES

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')
CONTRACT = 'CMP-LRM244-MODIFIER-WAIT'


def qualify(raw):
    report = deepcopy(raw)
    assert report['controller_exit_code'] == 0
    assert report['observations']['passed'] and report['observations']['status'] == 'FINISHED'
    assert set(report['checks']) == set(CASES)
    for key, source in CASES.items():
        assert report['checks'][key]['passed'], key
        assert report['checks'][key]['source'] == source, key
    for path, expected in report['inputs'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected, path
    verify_capture(report['runtime_sources']['integrated'], report['inputs'],
                   report.get('lf_normalized_inputs'))
    for dimension in DIMENSIONS:
        dependencies = [family+'-wait:'+dimension for family in ('gettm','verify','send','waitfor')]
        if dimension == 'boundary':
            dependencies += ['send-wait-override:boundary','waitfor-wait-override:boundary']
        if dimension in ('failure','recovery'):
            dependencies += ['internal-policy:'+dimension,'condition-strictness:'+dimension,
                             'wait-type:'+dimension,'send-false:'+dimension]
        assert all(report['checks'][key]['passed'] for key in dependencies)
        report['checks']['wait-composed:'+dimension] = dict(
            contracts=[CONTRACT], dimension=dimension, dependencies=dependencies, passed=True,
            oracle='All four original native function paths must pass their independent freshness, recorded-value, failure and recovery assertions, with strict handoff and no command replay.')
    report['qualified_contracts'] = [CONTRACT]
    report['scope'] = dict(
        manual='SPELL Language Reference2.4.4 pp37,40,44,54-57,113',
        supported='Wait fresh versus last recorded values in GetTM, Verify, Send verification and native WaitFor, including condition overrides and failure/recovery.',
        open='Complete Delay and Timeout rows, global Send Retries and general modifier composition, Prompt timeout conflict, interrupted waits, full Send/WaitFor, automatic limits and scheduled commands.',
        native='Original native executor and scheduler, original Python helper/verifier, real DSS binary acquisition and command receipts; no simulated language functions.',
        profile='Only the declared DSS catalog/profile and diagnostic composition chain are exercised.')
    report['full_v05_accepted'] = report['v06_dependency_satisfied'] = False
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    args = parser.parse_args()
    encoded = args.raw.read_bytes()
    report = qualify(json.loads(encoded))
    report['raw_report_sha256'] = hashlib.sha256(encoded).hexdigest()
    output = ROOT/'conformance/evidence/timing.json'
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(output), contracts=1, checks=len(report['checks']),
                         sha256=hashlib.sha256(output.read_bytes()).hexdigest()), indent=2))


if __name__ == '__main__':
    main()
