"""Independently verify what a real DAP client received for visible/hidden children."""
from pathlib import Path
from host_observation_review import ROOT,evidence,sha,read,ref
from child_visibility_cases import CASES

EXPECTED={
 'positive':({'child.py'},{'returned':True}),
 'boundary':(set(),{'returned':True}),
 'failure':({'bad.py'},{'rejected':True}),
 'recovery':({'child.py'},{'rejected':True,'recovered':True}),
}


def inspect(row,transcript,files,results,dimension):
    shown,parent=EXPECTED[dimension]
    assert row['dimension']==dimension and row['results']==results
    assert results['parent.json']==parent
    console=[m['body'] for m in transcript if m.get('event')=='output'
        and m.get('body',{}).get('category')=='console']
    assert console==row['console']
    grouped={}
    for item in console:
        path=item['source']['path'];name=Path(path).name
        assert name in shown
        grouped.setdefault(name,[]).append(item['output'])
    assert set(grouped)==shown
    for name,pieces in grouped.items():
        identity=results[name[:-3]+'.json']['instance']
        assert identity.startswith(name[:-3]+'#')
        assert ''.join(pieces)=='=== SPELL child '+identity+' ===\n'+files[name]+'=== End child source ===\n'
        assert sum(piece.startswith('=== SPELL child ') for piece in pieces)==1
    for name,result in results.items():
        if name!='parent.json':assert result['parent']=='main#1'
    assert not any('HIDDEN_CHILD_SOURCE_MARKER' in body['output'] for body in console)


def review(path,image,native_wheel,driver_wheel):
    raw,wheels=evidence(path,image,4,native_wheel,driver_wheel)
    assert set(raw['checks'])==set(EXPECTED)
    checks={}
    for name,row in raw['checks'].items():
        directory=path.parent/name;spec=CASES[name]
        assert (directory/'main.py').read_text(encoding='utf-8')==spec['parent']
        files={n:(directory/n).read_text(encoding='utf-8') for n in spec['files']}
        assert files==spec['files']
        results={n:read(directory/n) for n in ['parent.json',*spec['results']]}
        inspect(row,read(directory/'transcript.json'),files,results,name)
        checks['visible-source:'+name]=dict(passed=True,dimension=name,contracts=[],
            oracle='Actual client source frames match child files and native child identity; hidden execution has no source frames; failed/missing child and later execution retain visibility semantics.')
    inputs=dict(raw['inputs'])
    for name in ('conformance/host_observation_review.py','conformance/child_visibility_review.py'):
        inputs[name]=sha(ROOT/name)
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,raw=ref(path),
        composed_wheels=wheels,qualified_contracts=[],full_v05_accepted=False)
