"""Retain the corrected ranging-state evidence without automatic row promotion."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from rng_state_cases import CASES, METADATA
from installed_provenance import verify_capture
from rng_provenance import verify_composed

ROOT=Path(__file__).resolve().parents[1]


def qualify(raw):
    report=deepcopy(raw)
    assert report['controller_exit_code']==0
    assert report['observations']['passed'] and report['observations']['status']=='FINISHED'
    assert set(report['checks'])==set(CASES)
    for key,row in report['checks'].items():
        assert row['passed'] and row['source']==CASES[key],key
        assert row['contracts']==METADATA[key]['contracts']==[],key
        assert row['dimension']==METADATA[key]['dimension'],key
        assert len(row['prompts'])==len(row['expected_prompts']),key
    for name,expected in report['inputs'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    runtime=report['runtime_sources']
    verify_capture(runtime['integrated'],report['inputs'],report['lf_normalized_inputs'])
    composed=runtime.get('overlay') is None
    if composed:
        verify_composed(runtime,report['inputs'],report['lf_normalized_inputs'])
    else:
        assert set(runtime['overlay']['manifest'])=={'openbexi_spell_dss/ground.py'}
        assert set(runtime['base_overlay']['manifest'])=={'spell/lang/helpers/rnghelper.py','openbexi_dss_proxy/ranging.py'}
    for name in ('conformance/rng_state_report.py','conformance/RNG_STATE_RESULTS.md',
                 'tests/test_rng_state_patch.py','tests/test_rng_state_report.py'):
        report['inputs'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    report['qualified_contracts']=[]
    report['scope']=dict(
        manual='LRM2.4.4 p93 distinguishes periodic schedule control from on-demand ranging; p95 calibration is affected by Abort.',
        supported='Separate persistent schedule/activity state, original native single-path helpers, atomic idempotent migration, reopening and real pending-effect fencing.',
        boundaries='Virtual GENERIC simulator only; no periodic plan executor, RF, dual path, baseband ENG/RAW/list support, status constant mapping or generic native checkpoint qualification.',
        qualification='Zero new inventory rows promoted by this behavioral correction; full library contracts remain separately reviewed.',
        rollback='Old conflated-state runtime is not a qualified writer for the migrated database; rollback requires a compatible retained database snapshot.',
        distribution='Checked diagnostic overlay; fresh composition/RECORD and full release qualification remain separate gates.')
    if composed:
        report['scope']['distribution']='Fresh composed wheels with installed RECORD, recipe chains and helper/proxy/Ground bytes verified; full release qualification remains separate.'
    report.setdefault('retained_observation_arrays',{})
    for name in ('events','controls'):
        if name not in report['observations']:
            continue
        rows=report['observations'].pop(name)
        encoded=json.dumps(rows,sort_keys=True,separators=(',',':')).encode()
        report['retained_observation_arrays'][name]=dict(count=len(rows),canonical_json_sha256=hashlib.sha256(encoded).hexdigest())
    report['full_v05_accepted']=report['v06_dependency_satisfied']=False
    return report


def add_regression(report,path,count,profile):
    encoded=path.read_bytes()
    regression=json.loads(encoded)
    assert regression['passed'] and regression['exit_code']==0
    for name,expected in regression['inputs'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
        if name in report['inputs']:
            assert report['inputs'][name]==expected,name
        report['inputs'][name]=expected
    if profile=='separate-state':
        runtime=report['runtime_sources']
        if runtime.get('overlay') is None:
            row=verify_composed(runtime,report['inputs'],report['lf_normalized_inputs'])
            before,after=row['original_sha256'],row['patched_sha256']
        else:
            row=runtime['overlay']['manifest']['openbexi_spell_dss/ground.py']
            before,after=row['preimage_sha256'],row['sha256']
        assert regression['ground_preimage']==before
        assert regression['ground_patched']==after
    junit=path.with_name('junit.xml')
    suite=ET.fromstring(junit.read_bytes()).find('testsuite')
    assert suite is not None and int(suite.attrib['tests'])==count
    assert all(int(suite.attrib[key])==0 for key in ('failures','errors','skipped'))
    report.setdefault('regressions',{})[profile]=dict(
        path=str(path.resolve()),sha256=hashlib.sha256(encoded).hexdigest(),tests=count,
        junit_sha256=hashlib.sha256(junit.read_bytes()).hexdigest(),
        scope=regression.get('scope',regression.get('profile')))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path)
    parser.add_argument('--baseline',required=True,type=Path)
    parser.add_argument('--driver',required=True,type=Path)
    parser.add_argument('--legacy-and-migration',required=True,type=Path)
    args=parser.parse_args()
    encoded=args.raw.read_bytes()
    report=qualify(json.loads(encoded))
    baseline=json.loads(args.baseline.read_bytes())
    assert set(baseline['checks'])==set(CASES)
    for key in CASES:
        assert baseline['checks'][key]['source']==CASES[key],key
        assert not baseline['checks'][key]['passed'],key
    report['baseline']=dict(path=str(args.baseline.resolve()),sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        runtime_image=baseline['runtime_image'],failed={key:row['error'] for key,row in baseline['checks'].items()})
    report['raw_report_sha256']=hashlib.sha256(encoded).hexdigest()
    report['raw_report_path']=str(args.raw.resolve())
    add_regression(report,args.driver,28,'separate-state')
    add_regression(report,args.legacy_and_migration,47,'legacy-driver-and-migration')
    output=ROOT/'conformance/evidence/rng_state.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(output),checks=len(CASES),contracts=0)))


if __name__=='__main__':main()
