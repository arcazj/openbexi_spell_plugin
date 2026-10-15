"""Qualify only the bounded p89 examples and argument-pair syntax."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from child_arguments_cases import CASES
from installed_provenance import verify_capture

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution'))
from run_language_regressions import validate_report

CONTRACTS={'CMP-LRM244-'+name for name in ('EXAMPLE-160','EXAMPLE-161','SYNTAX-PROCEDURE-ARGUMENT')}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(raw_path):
    raw=json.loads(raw_path.read_bytes())
    validate_report(raw_path,raw['runtime_image'],len(CASES))
    assert raw['passed'] and not raw['timed_out']
    assert set(raw['checks'])==set(CASES)
    runtime=raw['runtime_sources']['integrated']
    assert runtime is not None
    verify_capture(runtime,raw['inputs'])
    assert raw['host_inputs']=={p.name:sha(p) for p in (ROOT/'host_runtime/python').glob('*.py')}
    for name,spec in CASES.items():
        row=raw['checks'][name]
        assert row['source']==spec['parent'] and row['child_source']==spec['child'],name
        assert row['contracts']==spec['contracts'] and row['dimension']==spec['dimension'],name
        assert row['parent_status']=='FINISHED' and row['parent_result']==spec['expected_parent'],name
        assert len(row['child_instances'])==spec['expected_children'],name
        assert all(status=='FINISHED' for status in row['child_statuses'].values()),name
        project=raw_path.parent/'workspace'/name.replace(':','-')
        assert (project/'main.py').read_text(encoding='utf-8')==spec['parent']
        assert (project/'child.py').read_text(encoding='utf-8')==spec['child']
        for file,key in (('events.json','events_sha256'),('native.log','native_log_sha256')):
            assert sha(project/file)==row[key],name
        assert not any(key.endswith('_error') for key in row),name
        if spec['expected_children']:
            assert row['child_result']==spec['expected_child'],name
        else:
            assert 'child_result' not in row and not (project/'child-result.json').exists(),name
    for contract in CONTRACTS:
        assert {row['dimension'] for row in raw['checks'].values() if contract in row['contracts']}=={
            'positive','boundary','failure','recovery'}
    report=deepcopy(raw)
    report.update(qualified_contracts=sorted(CONTRACTS),
        raw={'path':str(raw_path.resolve()),'sha256':sha(raw_path)},
        scope='Examples 160-161 and list-of-pairs args keyword syntax through real native parent and child executors.',
        exclusions=['Whole StartProc and argument-transfer section','Library priorities and named procedure headers',
                    'Non-blocking/manual/hidden modes','Complex argument object families','Checkpoint/warm-start recovery'])
    for name in ('conformance/child_arguments_report.py','conformance/CHILD_ARGUMENTS.md','tests/test_child_arguments_report.py'):
        report['inputs'][name]=sha(ROOT/name)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path)
    args=parser.parse_args()
    report=qualify(args.raw)
    output=ROOT/'conformance/evidence/child_arguments.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'output':str(output),'checks':len(CASES),'contracts':len(CONTRACTS)}))


if __name__=='__main__':
    main()
