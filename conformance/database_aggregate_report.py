"""Bind complete database operations to every native clause they depend on."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution'))
from run_language_regressions import SUITES,validate_report
from installed_provenance import verify_capture
from database_import_cases import CASES as IMPORT
from user_database_cases import CASES as USER
from scdb_cases import CASES as SCDB
from resource_cases import CASES as RESOURCE,METADATA as RESOURCE_META
from manoeuvre_database_cases import CASES as MANOEUVRE

DIMENSIONS=('positive','boundary','failure','recovery')
CATALOGS={'database-import':IMPORT,'user-database':USER,'scdb':SCDB,
          'resource':{name:dict(source=code,**RESOURCE_META[name]) for name,code in RESOURCE.items()},
          'manoeuvre':MANOEUVRE}
MINIMA={'database-import':16,'user-database':20,'scdb':26,'resource':12,'manoeuvre':8}
MAPPINGS={
    'CMP-LRM244-FUNCTION-CREATEDICTIONARY':('user-database','scdb','manoeuvre'),
    'CMP-LRM244-FUNCTION-LOADDICTIONARY':('user-database','manoeuvre'),
    'CMP-LRM244-FUNCTION-SAVEDICTIONARY':('user-database','scdb','manoeuvre'),
    'CMP-LRM244-SECTION-4-15-3-098':('database-import','resource'),
    'CMP-LRM244-SECTION-4-15-5-100':('user-database',),
    'CMP-LRM244-SYNTAX-URI-MMD':('manoeuvre',),
    'CMP-LRM244-SYNTAX-URI-USR':('user-database',),
}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())
ref=lambda p:dict(path=str(p.resolve()),sha256=sha(p))


def validate_component(suite,raw,image):
    assert raw['runtime_image']==image
    assert raw.get('passed',True) is True
    assert raw.get('controller_exit_code',raw.get('controller_exit',0))==0
    assert raw.get('timed_out',False) is False
    expected=set(CATALOGS[suite])
    if suite=='scdb':expected|={'checkpoint:on_line','checkpoint:on_step'}
    assert len(raw['checks'])==MINIMA[suite] and set(raw['checks'])==expected
    assert all(row['passed'] is True for row in raw['checks'].values())
    for name,spec in CATALOGS[suite].items():
        row=raw['checks'][name]
        assert all(row[key]==value for key,value in spec.items()),name
    verify_capture(raw['runtime_sources']['integrated'],raw['inputs'],raw.get('lf_normalized_inputs'))
    if suite=='user-database':
        assert set(raw['prompts'])=={'prompt-abort','prompt-rename'}
        for mode,count,status in [('abort',1,'ABORTED'),('rename',2,'FINISHED')]:
            prompt=raw['prompts']['prompt-'+mode]
            expected={'existing.IMP':'SAVED 42\n'}
            if mode=='rename':expected['renamed.IMP']='KEY\t7\n'
            assert prompt['passed'] is True and prompt['mode']==mode
            assert prompt['status']==status and len(prompt['prompts'])==count
            assert prompt['files']==expected
    if suite=='scdb':
        for name in ('checkpoint:on_line','checkpoint:on_step'):
            result=raw['checks'][name]['result']
            assert result['restored'] is True and result['shared_saved_alias'] is True
            assert result['alias_is_new_runtime_binding'] is True and result['readonly_type']=='ReadOnlyDatabase'


def component_checks(raws,image):
    assert set(raws)==set(MINIMA)
    for suite,raw in raws.items():validate_component(suite,raw,image)
    checks={}
    for contract,suites in MAPPINGS.items():
        for dimension in DIMENSIONS:
            components={suite:[name for name,row in raws[suite]['checks'].items()
                if row.get('dimension')==dimension] for suite in suites}
            assert all(components.values())
            checks[contract+':'+dimension]=dict(passed=True,contracts=[contract],dimension=dimension,
                components=components,required_complete_suites=list(suites),
                oracle='All native operation, persistence, URI, read-only and GDB mapping clauses pass on the same composed runtime; failure prompts preserve the original file.')
    return checks


def qualify(sequence_path,native_wheel,driver_wheel,root=ROOT):
    sequence=read(sequence_path)
    assert sequence['passed'] is True and sequence['state']=='completed' and sequence['complete_sequence'] is True
    assert [s['suite'] for s in sequence['suites']]==[s[0] for s in SUITES]
    image=sequence['image'];raws={};references={};inputs={}
    for stage,(_,_,_,minimum) in zip(sequence['suites'],SUITES):
        assert stage['passed'] is True and stage['exit_code']==0
        assert ref(Path(stage['log']['path']))==stage['log']
        path=Path(stage['raw']['path']);assert sha(path)==stage['raw']['sha256']
        assert validate_report(path,image,minimum,root=root)==stage['raw']
        if stage['suite'] in MINIMA:
            suite=stage['suite'];raws[suite]=read(path);references[suite]=ref(path)
            for name,digest in raws[suite]['inputs'].items():
                assert name not in inputs or inputs[name]==digest
                inputs[name]=digest
    checks=component_checks(raws,image)
    from manoeuvre_database_review import review
    manoeuvre=review(Path(references['manoeuvre']['path']),None,sequence['source_commit'],image,
        native_wheel=native_wheel,driver_wheel=driver_wheel)
    assert manoeuvre['passed'] is True
    from database_values_report import verify_archive
    verify_archive(Path(references['user-database']['path']),raws['user-database'],USER,True)
    assert set(MAPPINGS)<={r['id'] for r in read(root/'conformance/inventory.json')['rows']}
    inputs['conformance/database_aggregate_report.py']=sha(root/'conformance/database_aggregate_report.py')
    return dict(passed=True,runtime_image=image,inputs=inputs,sequence=ref(sequence_path),raw=references,
        checks=checks,qualified_contracts=sorted(MAPPINGS),component_counts=MINIMA,
        manoeuvre_review=manoeuvre,full_v05_accepted=False,
        scope='Seven complete database operation/URI contracts in the configured flat-file backend',
        remaining=['Whole database chapter and dictionary type','Database formats: key grammar and nested TIME values'])


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    for name in ('sequence','native-wheel','driver-wheel','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=qualify(args.sequence,args.native_wheel,args.driver_wheel)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,contracts=len(result['qualified_contracts']),output=str(args.output))))
