"""Bind the bounded Send correction without promoting whole inventory clauses."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from installed_provenance import verify_capture
from send_verify_cases import CASES

ROOT=Path(__file__).resolve().parents[1]


def qualify(raw):
    report=deepcopy(raw)
    assert report['controller_exit_code']==0
    assert report['observations']['passed'] and report['observations']['status']=='FINISHED'
    assert set(report['checks'])==set(CASES)
    for name,source in CASES.items():
        assert report['checks'][name]['passed'],name
        assert report['checks'][name]['source']==source,name
    for name,digest in report['inputs'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    verify_capture(report['runtime_sources']['integrated'],report['inputs'],report.get('lf_normalized_inputs'))
    overlay=report['runtime_sources']['diagnostic_overlay']['overlay']
    assert set(overlay)=={'limit-patch','timing-patch','send-verify-patch'}
    report['qualified_contracts']=[]
    report['scope']={'supported':'Bounded composed Send global Retries, IgnoreCase and ValueFormat with native effects and failure/recovery.',
                     'open':'Full Send, general modifier composition, full-family ValueFormat and all untested inventory dependencies.',
                     'manual':'LRM2.4.4 pp40,44,54,109,111',
                     'profile':'Original native executor plus checked Python-only diagnostic overlay and real DSS.'}
    report['full_v05_accepted']=report['v06_dependency_satisfied']=False
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path)
    args=parser.parse_args()
    data=args.raw.read_bytes()
    report=qualify(json.loads(data))
    report['raw_report_sha256']=hashlib.sha256(data).hexdigest()
    output=ROOT/'conformance/evidence/send_verify.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'output':str(output),'checks':len(report['checks']),'contracts':0}))


if __name__=='__main__':main()
