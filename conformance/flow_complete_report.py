"""Complete sub-procedure clauses require native modes, library and visible source."""
from aggregate_support import ROOT,PREFIX,DIMENSIONS,sha,read,ref,complete_sequence,merge_review_inputs,link_components

MAP={}
def bind(names,*groups):
    for name in names:
        assert name not in MAP;MAP[name]=groups

bind(('EXAMPLE-151',),'library','returns','visibility')
bind(('EXAMPLE-152','EXAMPLE-153','EXAMPLE-154','EXAMPLE-155','SECTION-4-16-1-1-109'),'library','returns')
bind(('EXAMPLE-157','MODIFIER-VISIBLE','SECTION-4-16-1-3-111'),'library','visibility','execution')
bind(('MODIFIER-AUTOMATIC',),'library','execution')
bind(('SECTION-4-16-1-5-113',),'arguments')
bind(('EXAMPLE-159','FUNCTION-STARTPROC','SECTION-4-16-1-108','SECTION-4-16-107'),
     'library','execution','policy','returns','arguments','visibility')

LIBRARY={
 'positive':('file-identifier','header-name','default-folder-order','configured-priority','configured-name-priority'),
 'boundary':('nested-file','configured-override','hidden-blocking','hidden-nonblocking','hidden-manual','complex-visible-manual'),
 'failure':(),
 'recovery':('missing-then-nested',),
}


def component_checks(reviewed):
    assert len({r['runtime_image'] for r in reviewed.values()})==1
    assert all(r['passed'] is True and all(row['passed'] is True for row in r['checks'].values()) for r in reviewed.values())
    checks={}
    for identifier,groups in MAP.items():
        for dimension in DIMENSIONS:
            dependencies=[]
            for kind in groups:
                if kind=='library':
                    selected=[('library',name) for name in LIBRARY[dimension]]
                    # Load rejection/recovery are performed in the original
                    # native resolver under every automatic/blocking mode.
                    if dimension in ('failure','recovery'):
                        selected += [('start',name) for name in reviewed['start']['checks'] if name.endswith('-'+dimension)]
                else:
                    selected=[(kind,name) for name,row in reviewed[kind]['checks'].items() if row.get('dimension')==dimension]
                assert selected
                for source,name in selected:
                    assert reviewed[source]['checks'][name]['passed'] is True
                    dependencies.append(dict(report=source,check=name))
            checks[PREFIX+identifier+':'+dimension]=dict(passed=True,dimension=dimension,
                contracts=[PREFIX+identifier],dependencies=dependencies,
                oracle='Original child resolver, selected file/header name, folder priorities, explicit path override, manual/automatic and blocking modes, failure policy, arguments, return values and actual visible/hidden client source are checked for this clause.')
    return link_components(checks,reviewed)


def qualify(sequence_path,native_wheel,driver_wheel):
    from procedure_library_review import review as library_review
    from child_start_report import qualify as start_review
    from child_return_report import qualify as return_review
    from child_execution_report import qualify as execution_review
    from child_policy_report import qualify as policy_review
    from child_arguments_report import qualify as arguments_review
    from child_visibility_review import review as visibility_review
    required=('child-start','child-modes','child-policy','child-arguments','child-visibility','procedure-library')
    sequence,paths,raws,inputs=complete_sequence(sequence_path,required)
    image,revision=sequence['image'],sequence['source_commit']
    reviewed=dict(
        library=library_review(paths['procedure-library'],None,revision,image,native_wheel=native_wheel,driver_wheel=driver_wheel),
        start=start_review(paths['child-start'],image),
        returns=return_review(paths['child-start'],paths['child-modes'],image),
        execution=execution_review(paths['child-start'],paths['child-modes'],image),
        policy=policy_review(paths['child-policy'],paths['child-start'],paths['child-modes'],image),
        arguments=arguments_review(paths['child-arguments']),
        visibility=visibility_review(paths['child-visibility'],image,native_wheel,driver_wheel))
    checks=component_checks(reviewed)
    assert len(MAP)==15
    merge_review_inputs(inputs,reviewed.values())
    for name in ('conformance/flow_complete_report.py','tests/test_flow_complete_mapping.py'):
        inputs[name]=sha(ROOT/name)
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,
        qualified_contracts=sorted(PREFIX+name for name in MAP),independent_reviews=reviewed,
        sequence=ref(sequence_path),raw={name:ref(path) for name,path in paths.items()},full_v05_accepted=False,
        scope='All remaining StartProc language clauses, including source shown in the actual DAP client for visible children and no source for hidden children.')
