"""Qualify only the demonstrated Event example and explicit RESEND constant."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from events_cases import CASES, METADATA
from installed_provenance import verify_capture

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = {'positive','boundary','failure','recovery'}
CONTRACTS = {'CMP-LRM244-EXAMPLE-110':'UI',
             'CMP-LRM244-CONSTANT-ACTION-RESEND':'COMMON'}


def qualify(raw):
    report = deepcopy(raw)
    assert report['controller_exit_code'] == 0
    assert report['observations']['passed'] and report['observations']['status'] == 'FINISHED'
    assert set(report['checks']) == set(CASES)
    for name,row in report['checks'].items():
        assert row['passed'] and row['source'] == CASES[name], name
        assert row['contracts'] == METADATA[name]['contracts'], name
        assert row['dimension'] == METADATA[name]['dimension'], name
        assert len(row['prompts']) == len(row['expected_prompts']), name
        for prompt,plan in zip(row['prompts'],row['expected_prompts']):
            assert prompt['answer'] == plan['answer'], name
            assert set(prompt['choices']) == set(plan['choices']), name
    for path,expected in report['inputs'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected,path
    verify_capture(report['runtime_sources'].get('integrated'),report['inputs'],report.get('lf_normalized_inputs'))
    report['qualified_contracts'] = sorted({c for row in report['checks'].values() for c in row['contracts']})
    assert set(report['qualified_contracts']) == set(CONTRACTS)
    inventory = {row['id']:row for row in json.loads((ROOT/'conformance/inventory.json').read_bytes())['rows']}
    for identifier,package in CONTRACTS.items():
        assert inventory[identifier]['package'] == package
        assert {r['dimension'] for r in report['checks'].values() if identifier in r['contracts']} == DIMENSIONS
    report['inputs']['conformance/events_report.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['scope'] = {
        'manual':'SPELL Language Reference 2.4.4 pp28,68-69,110-111,116-117',
        'event':'Example110 default INFORMATION, positional WARNING and keyword ERROR reach both original native client MSG_WRITE and durable event journal exactly once. Empty strings and UTF-8/newline payloads longer than 16384 characters are preserved. Invalid severity and scope codes raise the original native RuntimeError before journal delivery.',
        'resend':'Actual SAFE-mode CMD1 RELEASE/FAILED followed by a native OnFailure prompt. Every new attempt requires an explicit RESEND answer. Two failures then repair/success, or failure then CANCEL, have exact independent operation IDs and receipt counts.',
        'repair':'Controller recovery uses an independently identified real original-schema SET_MODE command, whose five DSS receipts are distinguished from procedure command attempts. No language function, registry entry or driver result is replaced.',
        'uncertain_effects':'Only definitive RELEASE/FAILED is resent. Unknown outcomes and stale authority are not treated as safe retries; existing CMD/native-driver regressions remain separate evidence.',
        'manual_interpretation':'Page28 defines RESEND as resending a command; page116 explicitly restricts this legacy action to Send command injection. Page117 distinguishes operation failures from normal False results. This suite uses actual operation failures and does not infer whole-group RESUME semantics.'
    }
    report['full_v05_accepted'] = report['v06_dependency_satisfied'] = False
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path)
    args=parser.parse_args()
    raw=args.raw.read_bytes()
    report=qualify(json.loads(raw))
    report['raw_report_sha256']=hashlib.sha256(raw).hexdigest()
    output=ROOT/'conformance/evidence/events.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(output),contracts=len(report['qualified_contracts']),
                         checks=len(report['checks']),sha256=hashlib.sha256(output.read_bytes()).hexdigest()),indent=2))


if __name__ == '__main__': main()
