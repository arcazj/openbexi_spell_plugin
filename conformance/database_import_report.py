"""Bind native configured database behavior to the declared explicit-import port."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from database_import_cases import CASES

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source_port'))
import database_import_patches as patch


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path)
    parser.add_argument('--baseline',required=True,type=Path)
    parser.add_argument('--files',required=True,type=Path)
    parser.add_argument('--data',required=True,type=Path)
    args=parser.parse_args()
    report=deepcopy(json.loads(args.raw.read_bytes()))
    assert report['controller_exit_code']==0 and set(report['checks'])==set(CASES)
    for name,spec in CASES.items():
        row=report['checks'][name]
        assert row['passed'] and all(row[key]==value for key,value in spec.items()),name
    for name,expected in report['inputs'].items():
        assert digest(ROOT/name)==expected,name
    with zipfile.ZipFile(ROOT/'docs/reference/SPELL2.6.10-src.zip') as archive:
        for name,preimage in patch.PREIMAGES.items():
            original=archive.read('src/spell/'+name)
            assert hashlib.sha256(original).hexdigest()==preimage
            expected=hashlib.sha256(patch.apply(name,original)).hexdigest()
            assert report['runtime_sources']['installed'][name]==expected
            assert report['runtime_sources']['manifests'][name]==dict(preimage=preimage,sha256=expected)
    contracts=sorted({value for row in CASES.values() for value in row['contracts']})
    inventory={row['id']:row for row in json.loads((ROOT/'conformance/inventory.json').read_bytes())['rows']}
    assert len(contracts)==5
    for contract in contracts:
        assert inventory[contract]['package']=='DATA'
        assert {row['dimension'] for row in CASES.values() if contract in row['contracts']}=={'positive','boundary','failure','recovery'}
    report['qualified_contracts']=contracts
    report['inputs']['conformance/database_import_report.py']=digest(Path(__file__))
    report['raw_report']=dict(path=str(args.raw.resolve()),sha256=digest(args.raw),
        native_logs_archive_sha256=digest(args.raw.parent/'workspace.tar'))
    baseline=json.loads(args.baseline.read_bytes())
    assert not baseline['checks']['ground:positive']['passed']
    assert not baseline['checks']['spacecraft-lookup:boundary']['passed']
    report['baseline']=dict(path=str(args.baseline.resolve()),sha256=digest(args.baseline),runtime_image=baseline['runtime_image'],
        failed=[name for name,row in baseline['checks'].items() if not row['passed']])
    report['regressions']={}
    for label,path,count in [('FILES',args.files,36),('DATA',args.data,24)]:
        regression=json.loads(path.read_bytes())
        assert regression['runtime_image']==report['runtime_image']
        assert len(regression['checks'])==count and all(row['passed'] for row in regression['checks'].values())
        report['regressions'][label]=dict(path=str(path.resolve()),sha256=digest(path),checks=count)
    report['scope']={
        'manual':'LRM2.4.4 pp78-80, real configured SCDB/GDB files parsed by the original DatabaseFile implementation under the native executor.',
        'namespace':'The established port requires explicit imports from spell.runtime, as documented in README/source_port/README and docs/EXECUTOR_COMMAND. Every procedure verifies startup already populated both runtime attributes before importing them and verifies Python builtins remain unchanged. Automatic database loading is demonstrated; implicit injection of SPELL names into ordinary Python globals is not claimed.',
        'ground':'Ground dictionary and calibration mappings load as typed original values, including false/empty/nested values, a large integer and UTF-8 text. Original DriverException for absent database keys and TypeError for invalid key objects remain catchable; successful reads recover after failures.',
        'spacecraft':'Only Examples135/136/137 are qualified: configured name lookup, keys iteration and the original custom database has_key method. Python built-in dict.has_key compatibility is not inferred.',
        'read_only_gap':'DATABASE-SCDB and its broader section stay open: the original DatabaseFile permits local assignment although p79 calls SCDB read-only. No read-only semantics were changed by these two importer patches.',
        'trusted_input':'Original trusted database-expression evaluation remains intact. The missing explicit os import caused its namespace construction to fail and silently return raw strings; this patch restores that namespace. Database files are not treated as an untrusted-data sandbox.',
        'distribution':'Development overlay with exact original/patched source and native binary identities. Fresh integrated wheel construction and final release qualification remain separate.'}
    report['full_v05_accepted']=report['v06_dependency_satisfied']=False
    output=ROOT/'conformance/evidence/database_import.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(output),contracts=len(contracts),checks=len(CASES),sha256=digest(output)),indent=2))


if __name__=='__main__':
    main()
