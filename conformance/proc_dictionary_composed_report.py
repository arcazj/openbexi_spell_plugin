"""Qualify procedure dictionaries on freshly installed composed packages."""
import argparse
import json
from pathlib import Path

from composed_diagnostic_proof import verify_donor
from proc_dictionary_report import ROOT, CANDIDATE_CONTRACTS, verify_cases, reference, sha, read


def qualify(baseline_path,lifecycle_path,image):
    inputs,checks,raw=verify_cases(baseline_path,lifecycle_path,image)
    lifecycle=read(lifecycle_path)
    assert not raw.get('diagnostic_overlay') and not lifecycle.get('diagnostic_overlay')
    assert raw['runtime_sources']==lifecycle['runtime_sources']
    donor=verify_donor(raw['runtime_sources']['integrated'],'proc_dictionary')
    for dimension in ('positive','boundary','failure','recovery'):
        checks['procedure-dictionary:'+dimension]['contracts']=CANDIDATE_CONTRACTS
    for name in ('conformance/proc_dictionary_composed_report.py','conformance/proc_dictionary_report.py',
                 'conformance/composed_diagnostic_proof.py','tests/test_proc_dictionary_composed_report.py'):
        inputs[name]=sha(ROOT/name)
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,
        qualified_contracts=CANDIDATE_CONTRACTS,diagnostic_donor=donor,
        raw={name:reference(path) for name,path in (('baseline',baseline_path),('lifecycle',lifecycle_path))},
        scope='LRM p81 PROC dictionary, root/child metadata and lifetime; p90 input/output paths',
        full_v05_accepted=False,full_v06_accepted=False,stable_v1_accepted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--lifecycle',type=Path,required=True)
    parser.add_argument('--image',required=True)
    args=parser.parse_args()
    report=qualify(args.baseline,args.lifecycle,args.image)
    output=ROOT/'conformance/evidence/proc_dictionary_composed.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(output),checks=len(report['checks']),contracts=len(CANDIDATE_CONTRACTS))))


if __name__=='__main__':main()
