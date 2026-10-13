"""Qualify bounded rows from retained native observations without changing coverage."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')
PREFIX = 'CMP-LRM244-'

# Demonstrating a useful subset must not silently assert these broader clauses.
EXCLUSIONS = {
    'FUNCTION-GETTM': 'Core acquisitions pass; the complete function also requires actual quality, validity and link-outage scenarios, still open.',
    'EXAMPLE-032': 'Relative timeout forms pass, but the literal one-minute example exceeds this driver profile\'s 30-second bound.',
    'EXAMPLE-040': 'Composite keys and values pass; the example\'s actual Display loop has not been asserted in native output.',
    'EXAMPLE-041': 'Underlying result detail is asserted; exact emitted failure-info text remains open.',
}
SECTION_DEPENDENCIES = {
    'SECTION-4-2-1-025': ['acquire'],
    'SECTION-4-2-2-026': ['raw'],
    'SECTION-4-2-3-027': ['extended', 'item-name', 'item-description', 'item-fullname', 'item-raw', 'item-eng', 'item-status', 'item-time', 'item-refresh'],
    'SECTION-4-3-1-031': ['single'] + ['operator-' + name for name in ('eq', 'neq', 'lt', 'le', 'gt', 'ge', 'bw', 'nbw')],
    'SECTION-4-3-2-032': ['verify-fresh', 'timeout-forms'],
    'SECTION-4-3-3-033': ['tolerance'],
    'SECTION-4-3-4-034': ['result'],
    'SECTION-4-3-5-035': ['false-noaction', 'false-automatic', 'false-default'],
    'SECTION-4-3-6-036': ['retries'],
    'SECTION-4-3-7-037': ['verify-delay'],
    'SECTION-4-3-8-038': ['ignore-case'],
    'SECTION-4-3-10-040': ['mixed-modifiers', 'result'],
    'SECTION-4-3-11-041': ['alternatives'],
    'SECTION-4-3-12-042': ['item-comparison', 'literal-name'],
    'SECTION-4-3-13-043': ['expression-and', 'expression-or', 'nested-expression'],
}


def qualify(raw):
    report = deepcopy(raw)
    assert report['controller_exit_code'] == 0
    assert report['observations']['passed'] and report['observations']['status'] == 'FINISHED'
    assert all(row['passed'] for row in report['checks'].values())
    for name, expected in report['inputs'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    checks = report['checks']
    all_sections = set()
    for row in checks.values():
        contracts = row.get('contracts', [])
        all_sections.update(item.removeprefix(PREFIX) for item in contracts if item.startswith(PREFIX + 'SECTION-'))
        row['contracts'] = [item for item in contracts if not item.startswith(PREFIX + 'SECTION-')
                            and item.removeprefix(PREFIX) not in EXCLUSIONS
                            and item != PREFIX + 'OUTCOME-VERIFY-PASS']
    assert all_sections == set(SECTION_DEPENDENCIES)
    for section, groups in SECTION_DEPENDENCIES.items():
        for dimension in DIMENSIONS:
            children = [group + ':' + dimension for group in groups]
            assert all(checks[key]['passed'] and checks[key]['dimension'] == dimension for key in children)
            checks['section:' + section + ':' + dimension] = dict(
                dimension=dimension, contracts=[PREFIX + section], passed=True,
                dependencies=children,
                oracle='LRM section is qualified only through all specifically enumerated supported child checks; no migration/rejection substitutes for support.')
    for dimension in DIMENSIONS:
        checks['verification-pass:' + dimension] = dict(
            dimension=dimension, contracts=[PREFIX + 'OUTCOME-VERIFY-PASS'], passed=True,
            dependencies=['operator-eq:' + dimension, 'result:' + dimension],
            oracle='Actual successful equality comparisons and True composite condition results, contrasted with False conditions, malformed definitions and subsequent successful recovery; a forced SKIP result is not a successful comparison.')
    report['inputs']['conformance/obs_report.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['manual_decisions'] = {
        'verify-false-action': {
            'explicit_text': {'page': 43, 'quote': 'This set of actions can be changed with the modifier OnFailure.'},
            'conflicting_detail': 'Pages41-42 explicitly describe OnFalse governing false comparison outcomes; Example42 sets OnFalse=NOACTION and Example43 sets OnFalse=SKIP.',
            'interpretation': 'Treat the final page43 OnFailure reference as an erratum in that false-outcome paragraph. Preserve OnFailure for acquisition and connection errors.',
            'native_evidence': ['false-actions-erratum:' + d for d in DIMENSIONS],
        },
        'retries': {
            'explicit_text': {'page': 42, 'quote': 'repeated at most two times using the next TM sample'},
            'context': 'The preceding clause says the first comparison has already evaluated False; the paragraph also explicitly says zero Retries performs no retries.',
            'interpretation': 'Retries=N means one initial attempt plus at most N additional attempts; this follows the explicit initial-comparison/repetition distinction, not a guessed inclusive loop convention.',
            'native_evidence': ['retries:' + d for d in DIMENSIONS],
            'independent_oracle': 'Actual original-schema RefreshItem requests: Retries2 yields [WaitFalse, WaitTrue, WaitTrue]; Retries0 yields one WaitFalse; every successful refresh has a real response.',
        },
        'verify-default': {
            'explicit_text': {'page': 41, 'description': 'Verify OnFalse defaults to ABORT | SKIP | RECHECK | CANCEL.'},
            'interpretation': 'Page114 is an illustrative spacecraft-dependent profile, not a second universal default.',
            'native_evidence': ['false-default:' + d for d in DIMENSIONS],
        },
    }
    report['explicit_open_clauses'] = {PREFIX + key: value for key, value in EXCLUSIONS.items()}
    inventory = {row['id']: row for row in json.loads((ROOT / 'conformance/inventory.json').read_text())['rows']}
    qualified = sorted({item for row in checks.values() for item in row.get('contracts', [])})
    assert all(item in inventory for item in qualified)
    for item in qualified:
        assert {row['dimension'] for row in checks.values() if item in row.get('contracts', [])} == set(DIMENSIONS)
    report['qualified_contracts'] = qualified
    report['full_v05_accepted'] = report['v06_dependency_satisfied'] = False
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw_report', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'conformance/evidence/obs.json')
    args = parser.parse_args()
    report = qualify(json.loads(args.raw_report.read_bytes()))
    report['raw_report_sha256'] = hashlib.sha256(args.raw_report.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(args.output), contracts=len(report['qualified_contracts']),
                          checks=len(report['checks']), image=report['runtime_image'],
                          sha256=hashlib.sha256(args.output.read_bytes()).hexdigest()), indent=2))


if __name__ == '__main__':
    main()
