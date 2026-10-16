"""Whole UI clauses include unrestricted event text and full prompt timeout behavior."""
from aggregate_support import ROOT,PREFIX,DIMENSIONS,sha,ref,complete_sequence,merge_review_inputs,link_components

MAP={
 'FUNCTION-EVENT':{'event':('event',)},
 'SECTION-4-10-083':{'event':('event',)},
 'MODIFIER-SEVERITY':{'event':('event',),'ui':('display',),'flow':('user-action',)},
 'SECTION-4-11-084':{'resource':('*',)},
 'FUNCTION-PROMPT':{'ui':('*',),'timed':('*',),'complete':('empty-default','typed-default','reminder')},
 'SECTION-4-12-085':{'ui':('*',),'timed':('*',),'complete':('empty-default','typed-default','reminder')},
 'TYPE-PROMPTRESULT':{'ui':('*',),'timed':('*',),'complete':('empty-default','typed-default','reminder')},
 'OUTCOME-PROMPT-TIMEOUT':{'timed':('*',),'complete':('empty-default','typed-default','reminder')},
}


def component_checks(reviewed):
    assert len({r['runtime_image'] for r in reviewed.values()})==1
    assert all(r.get('passed',True) is True and all(row['passed'] is True for row in r['checks'].values()) for r in reviewed.values())
    checks={}
    for identifier,groups in MAP.items():
        for dimension in DIMENSIONS:
            dependencies=[]
            for kind,features in groups.items():
                available=reviewed[kind]['checks']
                keys=([key for key,row in available.items() if row.get('dimension')==dimension]
                    if features==('*',) else [feature+':'+dimension for feature in features])
                assert keys
                dependencies += [dict(report=kind,check=key) for key in keys]
            checks[PREFIX+identifier+':'+dimension]=dict(passed=True,dimension=dimension,
                contracts=[PREFIX+identifier],dependencies=dependencies,
                oracle='Original native event delivery, severity, resource variables, typed prompt results, timed defaults, empty defaults and one unanswered reminder satisfy all selected clauses.')
    return link_components(checks,reviewed)


def qualify(sequence_path,native_wheel,driver_wheel,native_pair):
    from ui_native_review import review as ui_review
    from prompt_timeout_report import qualify as timed_review
    from prompt_complete_review import review as complete_review
    from event_text_review import review as event_review
    from resource_report import qualify as resource_review
    from installed_provenance import verify_capture
    required=('ui','prompt-timeout','prompt-complete','events','resource','flow')
    sequence,paths,raws,inputs=complete_sequence(sequence_path,required)
    image=sequence['image']
    # The flow runner independently checks native action configuration, IPC and
    # AsRun severities in all four dimensions; keep its complete source binding.
    flow=raws['flow'];assert flow['controller_exit_code']==0
    verify_capture(flow['runtime_sources']['integrated'],flow['inputs'])
    reviewed=dict(ui=ui_review(paths['ui'],image),
        timed=timed_review(paths['prompt-timeout'],ROOT/'conformance/evidence/prompt_timeout_baseline.json',native_pair),
        complete=complete_review(paths['prompt-complete'],image,native_wheel,driver_wheel),
        event=event_review(paths['events'],image,native_wheel,driver_wheel),resource=resource_review(raws['resource']),flow=flow)
    checks=component_checks(reviewed);merge_review_inputs(inputs,reviewed.values())
    for name in ('conformance/ui_complete_report.py','tests/test_ui_complete_mapping.py'):
        inputs[name]=sha(ROOT/name)
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,
        qualified_contracts=sorted(PREFIX+name for name in MAP),independent_reviews=reviewed,
        sequence=ref(sequence_path),raw={name:ref(path) for name,path in paths.items()},full_v05_accepted=False,
        scope='Eight remaining UI contracts; ranging ERROR is covered separately by the full ranging review. Host audio delivery and actual prompt lifecycle are checked alongside native typed results.')
