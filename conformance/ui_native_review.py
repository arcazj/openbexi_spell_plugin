"""Reconcile existing native UI checks with retained IPC and controller artifacts."""
from copy import deepcopy
from aggregate_support import ROOT,sha,read,ref
from installed_provenance import verify_capture
from run_language_regressions import validate_report


def review(path,image,source_root=ROOT):
    validate_report(path,image,62,root=source_root);raw=read(path);assert len(raw['checks'])==62
    verify_capture(raw['runtime_sources']['integrated'],raw['inputs'],raw.get('lf_normalized_inputs'))
    assert read(path.parent/'ui-runtime.json')==raw['runtime_sources']
    assert read(path.parent/'ui-complete.json')=={'completed':True}
    original=read(path.parent/'ui-results.json')['checks']
    edges=read(path.parent/'ui-edge-results.json')['checks']
    assert set(raw['checks'])==set(original)|set(edges)
    wire=read(path.parent/'ui-wire.json');answers=read(path.parent/'ui-answers.json')
    fields=[event['message']['fields'] for event in wire if event.get('message',{}).get('id')=='MSG_PROMPT']
    assert fields==[row['fields'] for row in answers]
    assert not any(row.get('event') in ('connectionError','unsupportedRequest') for row in wire)
    for key,row in original.items():
        assert row['passed'] is True and not row.get('error')
        actual=raw['checks'][key];assert actual['passed'] is True
        expected=row['expected'];observed=[item for item in answers if item['check']==key]
        assert observed==actual['controller_answers'] and len(observed)==len(expected['prompts'])
        for got,want in zip(observed,expected['prompts']):
            assert got['answer']==want['answer'] and got['fields']['Text']==want['text']
            assert (got['fields'].get('ExpectedValues','').split('\x04') if got['fields'].get('ExpectedValues') else [])==want['choices']
        for kind,identifier,selector in (('writes','MSG_WRITE','Text'),('items','MSG_NOTIFICATION','ItemName')):
            values=[item['message']['fields'] for item in wire if item.get('message',{}).get('id')==identifier
                and item['message']['fields'].get(selector,'').startswith('UI:'+key)]
            if key.startswith(('display:','notify:')):
                assert values==actual[kind] and len(values)==len(expected[kind])
                for want in expected[kind]:assert sum(all(value.get(k)==v for k,v in want.items()) for value in values)==1
    observations=read(path.parent/'ui-edge-observations.json')
    edge_wire=read(path.parent/'ui-edge-wire.json')
    assert len(observations)==15
    for name,row in observations.items():
        assert row['passed'] and row['entered'] and row['owned_cleanup']
        assert row['prompts']==[event['message']['fields'] for event in edge_wire if event.get('scenario')==name
            and event.get('message',{}).get('id')=='MSG_PROMPT']
        if name.endswith('-recovery'):
            kind=name.split('-')[0];expected={'list':('B','str'),'alpha':('Option 2','str'),'num':(1,'int')}[kind]
            assert row['status']=='FINISHED' and row['cleanup'] and row['continued']
            assert row['result']==dict(result=expected[0],type=expected[1])
        else:assert row['status']=='ABORTED' and not row['continued']
    for key,row in edges.items():assert raw['checks'][key]==row and row['passed']
    result=deepcopy(raw);result.update(passed=True,raw=ref(path),artifacts={p.name:sha(p) for p in path.parent.glob('ui-*.json')})
    result['inputs']['conformance/ui_native_review.py']=sha(ROOT/'conformance/ui_native_review.py')
    return result
