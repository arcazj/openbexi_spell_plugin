"""Bind native user database persistence and real prompt evidence to sources."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from user_database_cases import CASES

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source_port'))
import data_files_patches
import database_import_patches
import user_database_patches as patch


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path):
    return dict(path=str(path.resolve()),sha256=digest(path))


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
    chain={}
    with zipfile.ZipFile(ROOT/'docs/reference/SPELL2.6.10-src.zip') as archive:
        for name,preimage in patch.PREIMAGES.items():
            original=archive.read('src/spell/'+name)
            before=original
            stages=[]
            for recipe in (data_files_patches,database_import_patches):
                if name in recipe.PREIMAGES:
                    before=recipe.apply(name,before)
                    stages.append(dict(recipe=Path(recipe.__file__).name,sha256=hashlib.sha256(before).hexdigest()))
            assert hashlib.sha256(before).hexdigest()==preimage,name
            after=patch.apply(name,before)
            expected=hashlib.sha256(after).hexdigest()
            assert report['runtime_sources']['installed'][name]==expected
            assert report['runtime_sources']['manifest'][name]==dict(preimage=preimage,sha256=expected)
            chain[name]=dict(original_sha256=hashlib.sha256(original).hexdigest(),stages=stages,patched_sha256=expected)
    assert report['runtime_sources']['installed']['/opt/host/native.py']==digest(ROOT/'host_runtime/python/native.py')
    for mode,dimension in [('abort','failure'),('rename','recovery')]:
        prompt=report['prompts']['prompt-'+mode]
        assert prompt['passed'] and prompt['files']['existing.IMP']=='SAVED 42\n'
        assert len(prompt['prompts'])==(1 if mode=='abort' else 2)
        assert prompt['status']==('ABORTED' if mode=='abort' else 'FINISHED')
        identifier='create-prompt:'+dimension
        report['checks'][identifier]=dict(passed=True,dimension=dimension,
            contracts=CASES['create:'+dimension]['contracts'],
            oracle='Actual native MSG_PROMPT/MSG_ANSWER and terminal status, with independent original/new file bytes; abort preserves existing storage, retry requests a replacement name then creates and saves it.',
            observation=deepcopy(prompt))
        report['checks']['create:'+dimension]['dependencies']=[identifier]
    contracts=sorted({value for row in CASES.values() for value in row['contracts']})
    assert len(contracts)==10
    report['qualified_contracts']=contracts
    report['source_chain']=chain
    report['inputs']['conformance/user_database_report.py']=digest(Path(__file__))
    report['raw_report']=dict(**reference(args.raw),native_logs_archive_sha256=digest(args.raw.parent/'workspace.tar'))
    baseline=json.loads(args.baseline.read_bytes())
    assert not baseline['checks']['create:failure']['passed']
    assert not baseline['checks']['save:boundary']['passed']
    assert not baseline['prompts']['prompt-rename']['passed']
    unchanged={name:value for name,value in report['runtime_sources']['installed'].items() if name not in patch.PREIMAGES}
    assert all(baseline['runtime_sources']['installed'][name]==value for name,value in unchanged.items())
    report['baseline']=dict(**reference(args.baseline),runtime_image=baseline['runtime_image'],
        failed=[name for name,row in baseline['checks'].items() if not row['passed']],
        failed_prompts=[name for name,row in baseline['prompts'].items() if not row['passed']])
    report['regressions']={}
    for label,path,count in [('FILES',args.files,36),('DATA',args.data,24)]:
        regression=json.loads(path.read_bytes())
        assert regression['runtime_image']==report['runtime_image']
        assert len(regression['checks'])==count and all(row['passed'] for row in regression['checks'].values())
        report['regressions'][label]=dict(**reference(path),checks=count)
    report['scope']={
        'qualified':'LRM pp81-84, Examples143-148 and the four user database operation subsections, using original configured usr:// flat-file databases.',
        'creation':'Exclusive create preserves both existing file bytes and cached unsaved values; invalid paths/arity and unwritable directories fail. Real native failure prompts prove alternate-name retry and abort.',
        'saving':'Serialize before publication; write a same-directory temporary file, preserve original mode, fsync the new file and atomically replace the existing file. Missing or read-only storage and serialization failures preserve prior bytes and clean the temporary file. This is not a multiwriter transaction or directory-fsync crash-durability claim.',
        'round_trip':'UTF-8 literal strings/containers preserve quotes, backslashes and internal whitespace; binary width and exact top-level absolute/relative TIME are serialized without global display-format dependence. Comment-like keys, cyclic/custom values and nonfinite floats are rejected before replacement.',
        'open':'Full database-formats section remains open: legacy 035 spelling, non-string file keys, nested TIME/custom value serialization and broad database backends are not claimed. Configured SCDB read-only semantics remain a separate tranche.',
        'distribution':'Exact development overlay identities; installed wheel RECORD is superseded for these three modules. Fresh integrated wheel and complete release qualification are separate.'}
    report['full_v05_accepted']=report['v06_dependency_satisfied']=False
    output=ROOT/'conformance/evidence/user_database.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(output),contracts=len(contracts),checks=len(report['checks']),sha256=digest(output)),indent=2))


if __name__=='__main__':
    main()
