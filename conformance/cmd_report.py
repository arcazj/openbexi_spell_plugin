"""Select only explicitly demonstrated command contracts from native evidence."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = ('positive','boundary','failure','recovery')
PREFIX = 'CMP-LRM244-'
SECTIONS = {
    'SECTION-4-5-1-047': ['send-name','send-item'],
    'SECTION-4-5-5-051': ['confirm'],
    'SECTION-4-5-9-055': ['group-names','group-items'],
}


def qualify(raw):
    report = deepcopy(raw)
    assert report['controller_exit_code'] == 0
    assert report['observations']['passed'] and report['observations']['status'] == 'FINISHED'
    assert all(row['passed'] for row in report['checks'].values())
    for path, expected in report['inputs'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected,path
    for row in report['checks'].values():
        row['contracts'] = [c for c in row['contracts'] if not c.startswith(PREFIX+'SECTION-')]
    for section, groups in SECTIONS.items():
        for dimension in DIMENSIONS:
            children = [group+':'+dimension for group in groups]
            if section == 'SECTION-4-5-9-055' and dimension in ('failure','recovery'):
                children += ['partial-group:'+dimension,'group-failure-prompt:'+dimension]
                if dimension == 'failure': children += ['group-empty:failure']
            assert all(report['checks'][key]['passed'] for key in children)
            report['checks']['section:'+section+':'+dimension] = dict(
                contracts=[PREFIX+section],dimension=dimension,dependencies=children,passed=True,
                oracle='All explicitly named supported child checks are mandatory; broader parent command sections remain open.')
    report['qualified_contracts'] = sorted({c for row in report['checks'].values() for c in row['contracts']})
    inventory = {row['id']:row for row in json.loads((ROOT/'conformance/inventory.json').read_bytes())['rows']}
    for identifier in report['qualified_contracts']:
        assert inventory[identifier]['package'] == 'CMD'
        assert {r['dimension'] for r in report['checks'].values() if identifier in r['contracts']} == set(DIMENSIONS)
    report['inputs']['conformance/cmd_report.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['scope'] = {
        'manual':'SPELL Language Reference2.4.4 pp47–55',
        'supported':'Basic construction, Send(name/item), demonstrated argument syntax and catalog encoding, ordinary sequential lists with actual partial failures, confirmation and explicit recovery.',
        'open':'Full BuildTC/Send and command argument types/casting, GCS sequences, scheduling, load-only, critical confirmation, platform addInfo, atomic Group/Block and combined telemetry/limit behavior are not qualified.',
        'block_validation':'Malformed flags and empty blocks reject before effects. Supported Group/Block behavior is qualified by the separate command/display composition report.',
        'failure_oracle':'Actual simulator SAFE mode: CMD2 succeeds, CMD1 has RELEASE/FAILED, CMD3 remains unsent. Both automatic cancellation and native ABORT/RESEND/SKIP/CANCEL action prompt are asserted.',
        'uncertain_effects':'Retained separately by original driver and native DSS regression suites; known false receipts and unknown outcomes are not interchangeable.'
    }
    report['full_v05_accepted'] = report['v06_dependency_satisfied'] = False
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path)
    args = parser.parse_args()
    raw = args.raw.read_bytes()
    report = qualify(json.loads(raw))
    report['raw_report_sha256'] = hashlib.sha256(raw).hexdigest()
    output = ROOT/'conformance/evidence/cmd.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(output),contracts=len(report['qualified_contracts']),checks=len(report['checks']),sha256=hashlib.sha256(output.read_bytes()).hexdigest()),indent=2))


if __name__ == '__main__': main()
