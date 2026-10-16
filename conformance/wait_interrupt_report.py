"""Bind the native interruption correction to its retained late-acquisition failure."""
import argparse
import hashlib
import json
from pathlib import Path

from wait_control_report import ROOT,qualify as qualify_controls

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def qualify(path,baseline_path,image):
    report=qualify_controls(path,image)
    raw=json.loads(path.read_bytes());baseline=json.loads(baseline_path.read_bytes())
    assert raw['diagnostic_overlay'] and report['qualified_contracts']==[]
    assert baseline['runtime_sources']['integrated']==raw['runtime_sources']['baseline']
    assert not baseline['passed'] and not baseline['timed_out'] and len(baseline['checks'])==24
    assert {k for k,v in baseline['checks'].items() if not v['passed']}=={'telemetry:skip:recovery'}
    for name,digest in baseline['inputs'].items():assert sha(ROOT/name)==digest,name
    failed=baseline['checks']['telemetry:skip:recovery']
    assert 'Telemetry continued while interrupted' in failed['error']
    first=next(r['monotonic'] for r in failed['states'] if r['status']=='INTERRUPTED')
    assert all(r['status']=='INTERRUPTED' for r in failed['states'] if r['monotonic']>=first)
    assert any(r['path'].endswith('/RefreshItem') and r['started']>first+.3 for r in failed['rpc'])
    report['baseline']=dict(path=str(baseline_path.resolve()),sha256=sha(baseline_path))
    report['qualification_identity']=raw['qualification_identity']
    report['scope']='Diagnostic one-library interruption correction; fresh composed packages remain required'
    for name in ('conformance/wait_interrupt_report.py','tests/test_wait_interrupt_report.py'):
        report['inputs'][name]=sha(ROOT/name)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path);parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--image',required=True)
    args=parser.parse_args();report=qualify(args.raw,args.baseline,args.image)
    path=ROOT/'conformance/evidence/wait_interrupt.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(path),checks=len(report['checks']),qualified_contracts=[])))


if __name__=='__main__':main()
