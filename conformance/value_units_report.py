"""Qualify only complete native BuildTC ValueType/Units modifier evidence."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from value_units_cases import CASES, METADATA
from installed_provenance import verify_capture

ROOT=Path(__file__).resolve().parents[1]
DIMENSIONS={'positive','boundary','failure','recovery'}
CONTRACTS={'CMP-LRM244-MODIFIER-VALUETYPE','CMP-LRM244-MODIFIER-UNITS'}


def qualify(raw):
    report=deepcopy(raw)
    assert report['controller_exit_code']==0
    assert report['observations']['passed'] and report['observations']['status']=='FINISHED'
    assert set(report['checks'])==set(CASES)
    for key,row in report['checks'].items():
        assert row['passed'],key
        assert row['source']==CASES[key],key
        assert row['contracts']==METADATA[key]['contracts'],key
    for name,digest in report['inputs'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    verify_capture(report['runtime_sources'].get('integrated'),report['inputs'],report.get('lf_normalized_inputs'))
    contracts={c for row in report['checks'].values() for c in row['contracts']}
    assert contracts==CONTRACTS
    for contract in CONTRACTS:
        assert {row['dimension'] for row in report['checks'].values() if contract in row['contracts']}==DIMENSIONS
    report['qualified_contracts']=sorted(CONTRACTS)
    report['inputs']['conformance/value_units_report.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['scope']=dict(manual='LRM2.4.4 pp48,112-113',
        supported='Original native BuildTC casts/inference and exact unit-name preservation; atomic invalid argument replacement and actual catalog-supported command receipts.',
        decisions='Python truthiness for BOOLEAN; TIME constructor resolves existing DATETIME/RELTIME metadata; Units is a name, without invented catalog conversion.',
        open='Full BuildTC/Send, calibration and arbitrary unit/TIME command transmission, scheduled commands and atomic groups.',
        driver_bounds='Unsupported unit/type transmission is explicitly rejected without effects; this is not support promotion.')
    report['full_v05_accepted']=report['v06_dependency_satisfied']=False
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path)
    args=parser.parse_args()
    raw=args.raw.read_bytes()
    report=qualify(json.loads(raw))
    report['raw_report_sha256']=hashlib.sha256(raw).hexdigest()
    output=ROOT/'conformance/evidence/value_units.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(output),contracts=len(CONTRACTS),checks=len(CASES),sha256=hashlib.sha256(output.read_bytes()).hexdigest())))


if __name__=='__main__':
    main()
