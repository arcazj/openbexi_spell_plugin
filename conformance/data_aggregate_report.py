"""Close whole data contracts only when every native component has passed."""
import hashlib,json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution'))
from run_language_regressions import SUITES,validate_report
from installed_provenance import verify_capture

DIMENSIONS=('positive','boundary','failure','recovery')
DTA_GROUPS=('typed-long','typed-float','typed-boolean','typed-string','typed-datetime','typed-reltime',
    'mapping','declarations','constraints','initialization','confirmation','formats','deferred-format',
    'literal-inputs','notifications','time-constraints','time-precision')
DATA_GROUPS=('primitive-values','batch-values','compare-and-set','scope-isolation','clear-scopes','global-scope')
MAPPINGS={
    'CMP-LRM244-TYPE-VAR':('dta',),
    'CMP-LRM244-SECTION-1-2-106':('dta','dta-ipc'),
    'CMP-LRM244-MODIFIER-EXPECTED':('dta','data','data-race'),
    'CMP-LRM244-MODIFIER-SCOPE':('data','data-race'),
    'CMP-LRM244-SECTION-4-19-129':('data','data-race'),
    'CMP-LRM244-FUNCTION-CANDIDATE-CLEARSHAREDDATASCOPE':('data',),
}
MINIMA={'dta':68,'dta-ipc':64,'data':24,'data-race':4}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())
ref=lambda p:dict(path=str(p.resolve()),sha256=sha(p))


def component_checks(raws,image):
    assert set(raws)==set(MINIMA)
    for suite,raw in raws.items():
        assert raw['runtime_image']==image
        assert raw.get('controller_exit',raw.get('controller_exit_code',0))==0
        assert raw.get('passed',True) is True
        assert len(raw['checks'])==MINIMA[suite]
        assert all(row['passed'] is True for row in raw['checks'].values())
        verify_capture(raw['runtime_sources']['integrated'],raw['inputs'],raw.get('lf_normalized_inputs'))
    expected=lambda groups:{g+':'+d for g in groups for d in DIMENSIONS}
    assert set(raws['dta']['checks'])==expected(DTA_GROUPS)
    assert set(raws['data']['checks'])==expected(DATA_GROUPS)
    assert set(raws['data-race']['checks'])==expected(('competing-executors',))
    assert raws['dta-ipc']['passed'] and raws['dta-ipc']['continued_after_edits']
    for suite in raws:
        assert {r['dimension'] for r in raws[suite]['checks'].values()}==set(DIMENSIONS)
    checks={}
    for contract,suites in MAPPINGS.items():
        for dimension in DIMENSIONS:
            components={suite:[name for name,row in raws[suite]['checks'].items() if row['dimension']==dimension] for suite in suites}
            assert all(components.values())
            checks[contract+':'+dimension]=dict(passed=True,contracts=[contract],dimension=dimension,
                components=components,oracle='All required native typed-value, CIF notification/editing and context blackboard observations pass; no component or dimension is omitted')
    return checks


def scope_spelling(root=ROOT):
    """The singular prose name denotes the plural callable in Example 189."""
    from pypdf import PdfReader
    manual=root/'docs/reference/SPELL - Language Reference - 2.4.4.pdf'
    archive=root/'docs/reference/SPELL2.6.10-src.zip'
    pages=PdfReader(manual)
    prose=pages.pages[98].extract_text();index=pages.pages[103].extract_text()
    assert 'ClearSharedDataScope function' in prose
    assert 'ClearSharedDataScopes()' in prose and "ClearSharedDataScopes( 'scope' )" in prose
    assert 'ClearSharedDataScopes' in index
    with zipfile.ZipFile(archive) as z:
        member='src/spell/spell/lang/functions.py'
        source=z.read(member)
    assert b'def ClearSharedDataScope(' not in source
    assert source.count(b'def ClearSharedDataScopes(')==1
    return dict(manual=ref(manual),archive=ref(archive),pages=[99,104],member=member,
        member_sha256=hashlib.sha256(source).hexdigest(),inventory_label='ClearSharedDataScope',
        demonstrated_callable='ClearSharedDataScopes',interpretation='Singular prose typo; Example 189, the index and the original source agree on the plural callable. Inventory identity is preserved.')


def qualify(sequence_path,root=ROOT):
    sequence=read(sequence_path)
    assert sequence['passed'] and sequence['state']=='completed' and sequence['complete_sequence']
    assert [s['suite'] for s in sequence['suites']]==[s[0] for s in SUITES]
    image=sequence['image'];raws={};references={};inputs={}
    for stage,(_,_,_,minimum) in zip(sequence['suites'],SUITES):
        assert stage['passed'] and stage['exit_code']==0
        assert ref(Path(stage['log']['path']))==stage['log']
        path=Path(stage['raw']['path'])
        assert sha(path)==stage['raw']['sha256']
        assert validate_report(path,image,minimum,root=root)==stage['raw']
        if stage['suite'] in MINIMA:
            raw=read(path);raws[stage['suite']]=raw;references[stage['suite']]=ref(path)
            for name,digest in raw['inputs'].items():
                assert name not in inputs or inputs[name]==digest
                inputs[name]=digest
    checks=component_checks(raws,image)
    spelling=scope_spelling(root)
    inventory=read(root/'conformance/inventory.json')
    assert len(inventory['rows'])==763 and set(MAPPINGS)<={r['id'] for r in inventory['rows']}
    inputs['conformance/data_aggregate_report.py']=sha(root/'conformance/data_aggregate_report.py')
    return dict(passed=True,runtime_image=image,inputs=inputs,raw=references,sequence=ref(sequence_path),
        checks=checks,qualified_contracts=sorted(MAPPINGS),scope_spelling=spelling,full_v05_accepted=False,
        component_counts=MINIMA,scope='Six whole data contracts from complete native component coverage; other release requirements remain separate')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--sequence',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=qualify(args.sequence)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,contracts=len(result['qualified_contracts']),output=str(args.output))))
