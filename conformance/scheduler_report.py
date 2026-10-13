"""Bind the two bounded scheduler modifiers to all traced native observations."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from scheduler_scenarios import SCENARIOS
from installed_provenance import verify_capture

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS={'CMP-LRM244-MODIFIER-UNTIL','CMP-LRM244-MODIFIER-MESSAGE'}


def qualify_observation(name, check, observations, spec):
    """Separate the recorder's exact scenario link from check dependencies."""
    assert check.get('dependencies') == [name], (name, 'unexpected observation link')
    assert 'observation_dependencies' not in check, (name, 'ambiguous observation link')
    assert name in observations, (name, 'missing observation')
    actual=observations[name]
    assert check['passed'] and actual['passed'] and actual['status']=='FINISHED',name
    assert actual['asrun'],name
    assert check['contracts']==spec['contracts'] and check['dimension']==spec['dimension'],name
    check['observation_dependencies']=check.pop('dependencies')


def qualify(raw):
    report=deepcopy(raw)
    assert report['controller_exit_code']==0
    assert set(report['checks'])==set(SCENARIOS)==set(report['observations'])
    for name,spec in SCENARIOS.items():
        qualify_observation(name,report['checks'][name],report['observations'],spec)
    for path,expected in report['inputs'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,path
    manifest=report['runtime_sources'].get('scheduler_manifest')
    integrated=report['runtime_sources'].get('integrated')
    installed=report['runtime_sources']['installed']
    if integrated:
        verify_capture(integrated,report['inputs'],report.get('lf_normalized_inputs'))
        composition=integrated['manifest']['composition']['native']
        assert 'scheduler_patches.py' in composition['recipes']
        assert all(name in composition['sources'] for name in (
            'lib/SPELL_EXC/src/SPELLexecutorUtils.C',
            'lib/SPELL_EXC/src/SPELLexecutorPython.C',
            'lib/SPELL_EXC/src/SPELLscheduler.C'))
        artifacts=integrated['native_artifacts']
    else:
        assert manifest and len(manifest['source_hashes'])==3
        artifacts=manifest['artifacts']
    for name,digest in artifacts.items():
        assert installed['/usr/local/lib/python3.13/site-packages/spell_native/bin/'+name]==digest,name
    report['qualified_contracts']=sorted({c for row in report['checks'].values() for c in row['contracts']})
    assert set(report['qualified_contracts'])==CONTRACTS
    inventory={r['id']:r for r in json.loads((ROOT/'conformance/inventory.json').read_bytes())['rows']}
    for identifier in CONTRACTS:
        assert inventory[identifier]['package']=='COMMON'
        assert {r['dimension'] for r in report['checks'].values() if identifier in r['contracts']}=={'positive','boundary','failure','recovery'}
    report['inputs']['conformance/scheduler_report.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['scope']=dict(manual='LRM2.4.4 pp58-59,112-113',
        supported='Absolute Until targets and progress Message text through the original native scheduler, with four dimensions each and integer-interval control.',
        open='Whole WaitFor, interrupt/resume, telemetry waits, cross-family Delay/Timeout/Wait, all Interval semantics and full v0.5/v0.6 acceptance.',
        inherited=('Verified installed native/Python composition and matching driver composition; the exact image and all recipe inputs are recorded. Package identity does not imply full conformance.' if integrated else
            'Exact integrated diagnostic dc15d9f1f6de retained as compiler source and runtime composition; latest Python tree and all native executables copied together. Its original obsolete DTA oracle failure is not an accepted release claim.'))
    report['full_v05_accepted']=report['v06_dependency_satisfied']=False
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path)
    args=parser.parse_args()
    raw=args.raw.read_bytes()
    report=qualify(json.loads(raw))
    report['raw_report_sha256']=hashlib.sha256(raw).hexdigest()
    output=ROOT/'conformance/evidence/scheduler.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(output),checks=len(report['checks']),contracts=len(CONTRACTS),
                         sha256=hashlib.sha256(output.read_bytes()).hexdigest()),indent=2))


if __name__=='__main__':main()
