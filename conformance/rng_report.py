"""Qualify only the complete, explicitly bounded native ranging slice."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from rng_cases import CASES, METADATA
from installed_provenance import verify_capture
from rng_composed_review import verify_composed

ROOT=Path(__file__).resolve().parents[1]
DIMENSIONS={'positive','boundary','failure','recovery'}
CATALOG_CASES={key for key in CASES if key.startswith(('baseband-names:','antenna-names:'))}
CONTRACTS={'CMP-LRM244-'+name for name in (
    'FUNCTION-GETBASEBANDNAMES','FUNCTION-GETANTENNANAMES','EXAMPLE-174')}
EXCLUDED={'CMP-LRM244-'+name:reason for name,reason in (
    ('FUNCTION-ENABLERANGING','LRM p93 requires schedule control distinct from on-demand activity; the current ground profile conflates both states.'),
    ('FUNCTION-DISABLERANGING','LRM p93 requires schedule control distinct from on-demand activity; the current ground profile conflates both states.'),
    ('EXAMPLE-169','Enabling/disabling while an activity is active has not been qualified independently of activity state.'),
    ('EXAMPLE-170','The current profile rejects on-demand start while schedule is disabled; this observed behavior is not a manual oracle.'),
    ('EXAMPLE-172','Aborting must be qualified without implicitly enabling a previously disabled schedule.'),
    ('EXAMPLE-175','Calibration activity and periodic schedule require independent state and controls.'))}


def qualify(raw):
    report=deepcopy(raw)
    assert report['controller_exit_code']==0
    assert report['observations']['passed'] and report['observations']['status']=='FINISHED'
    composed=report['runtime_sources'].get('overlay') is None
    assert set(report['checks'])==(CATALOG_CASES if composed else set(CASES))
    if composed:
        assert report['selection']=='catalog'
    for key,row in report['checks'].items():
        assert row['passed'] and row['source']==CASES[key],key
        assert row['contracts']==METADATA[key]['contracts'],key
        assert row['dimension']==METADATA[key]['dimension'],key
        assert len(row['prompts'])==len(row['expected_prompts']),key
    for name,digest in report['inputs'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    runtime=report['runtime_sources']
    assert runtime['integrated'] and runtime['integrated']['driver_composition']
    verify_capture(runtime['integrated'],report['inputs'],report['lf_normalized_inputs'])
    if composed:
        verify_composed(runtime,report['inputs'],report['lf_normalized_inputs'])
    else:
        assert set(runtime['overlay']['manifest'])=={'spell/lang/helpers/rnghelper.py','openbexi_dss_proxy/ranging.py'}
    actual={name for row in report['checks'].values() for name in row['contracts']}
    assert actual==(CONTRACTS if composed else CONTRACTS|set(EXCLUDED))
    for row in report['checks'].values():
        excluded=[name for name in row['contracts'] if name in EXCLUDED]
        if excluded:
            row['observed_contracts']=excluded
            row['contracts']=[name for name in row['contracts'] if name not in EXCLUDED]
            row['qualification_scope']='Diagnostic current-profile observation only; schedule/activity semantics remain open.'
    for contract in CONTRACTS:
        assert {row['dimension'] for row in report['checks'].values() if contract in row['contracts']}==DIMENSIONS
    if composed:
        # Example 174 contains both list calls; one catalog alone cannot support it.
        example='CMP-LRM244-EXAMPLE-174'
        for row in report['checks'].values():
            row['contracts']=[name for name in row['contracts'] if name!=example]
        for dimension in sorted(DIMENSIONS):
            dependencies=[name+':'+dimension for name in ('baseband-names','antenna-names')]
            report['checks']['catalog-example174:'+dimension]=dict(
                passed=all(report['checks'][key]['passed'] for key in dependencies),
                contracts=[example],dimension=dimension,dependencies=dependencies,
                oracle='LRM p95 Example 174 requires both known-baseband and known-antenna lists; both native controls must pass.')
    report['qualified_contracts']=sorted(CONTRACTS)
    report['excluded_contracts']=EXCLUDED
    if composed:
        report['excluded_contracts']={name:'Separate schedule/activity controls are retained; this catalog run does not qualify the complete manual contract.' for name in EXCLUDED}
    report['inputs']['conformance/rng_report.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for name in ('conformance/rng_composed_review.py','conformance/RNG_RESULTS.md','tests/test_rng_report.py','docs/reference/SPELL - Driver Development Manual - 2.4.4.pdf'):
        report['inputs'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    report['scope']=dict(
        manual='LRM 2.4.4 pp93–95; no manual erratum introduced.',
        supported='Known baseband/antenna name lists in the declared GENERIC simulator; three catalog rows only.',
        observed='Helper arity and calibration method fixes, exact-bool local policy filtering, native prompts and actual persistent binary RPC receipts. The existing one-state schedule/activity model is a documented defect, not normative qualification.',
        open='Schedule/activity separation including enable/disable/start/abort/calibration clauses, dual paths, whole functions and sections, baseband list/ENG/RAW configuration, GetRangingStatus constant conflict, RF hardware and other drivers.',
        execution='Imported independent oracle calls original native helpers; generic warm-start/checkpoint recovery is not claimed.',
        distribution='Python-only diagnostic overlay on an independently rebuilt native checkpoint. Fresh composed wheels and complete release qualification remain separate.')
    if composed:
        report['scope'].update(
            observed='Eight catalog controls through original native helpers and the persistent GENERIC driver; activity semantics are qualified separately.',
            open='Full schedule/activity library contracts and periodic plan execution, dual paths, baseband list/ENG/RAW configuration, GetRangingStatus constant conflict, RF hardware and other drivers.',
            distribution='Fresh composed wheels with installed RECORD, recipe chains and helper/proxy/Ground bytes verified; complete release acceptance remains separate.')
    retained={}
    for name in ('events','controls'):
        if name in report['observations']:
            rows=report['observations'].pop(name)
            encoded=json.dumps(rows,sort_keys=True,separators=(',',':')).encode()
            retained[name]=dict(count=len(rows),canonical_json_sha256=hashlib.sha256(encoded).hexdigest())
    if retained:
        report['retained_observation_arrays']=retained
    report['full_v05_accepted']=report['v06_dependency_satisfied']=False
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path)
    parser.add_argument('--baseline',required=True,type=Path)
    args=parser.parse_args()
    encoded=args.raw.read_bytes()
    report=qualify(json.loads(encoded))
    baseline=json.loads(args.baseline.read_bytes())
    assert set(baseline['checks'])==set(CASES)
    for key in CASES:
        assert baseline['checks'][key]['source']==CASES[key],key
    assert all(not baseline['checks'][key]['passed'] for key in (
        'enable:failure','disable:failure','calibration-single:positive'))
    report['baseline']=dict(path=str(args.baseline.resolve()),
        sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        runtime_image=baseline['runtime_image'],
        failed={key:dict(error=row['error'][:300],full_error_sha256=hashlib.sha256(row['error'].encode()).hexdigest())
                for key,row in baseline['checks'].items() if not row['passed']})
    report['raw_report_sha256']=hashlib.sha256(encoded).hexdigest()
    report['raw_report_path']=str(args.raw.resolve())
    output=ROOT/'conformance/evidence/rng.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(output),checks=len(report['checks']),contracts=len(CONTRACTS))))


if __name__=='__main__':
    main()
