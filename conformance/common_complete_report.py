"""Cross-family modifiers require every applicable native service family."""
from aggregate_support import ROOT,PREFIX,DIMENSIONS,sha,ref,complete_sequence,merge_review_inputs,link_components

MAP={
 'CONSTANT-ACTION-RESUME':('extension',),
 'CONSTANT-VALUE-FORMAT-ENG':('observation','command','special','data'),
 'CONSTANT-VALUE-FORMAT-RAW':('observation','command','special','data'),
 'MODIFIER-DEFAULT':('ui','data','common'),
 'MODIFIER-DELAY':('command','observation'),
 'MODIFIER-END':('special','command','time'),
 'MODIFIER-ERROR':('limits','special','common','database'),
 'MODIFIER-FORMAT':('observation','command','special','data','database','values'),
 'MODIFIER-IGNORE':('limits','observation','common','database'),
 'MODIFIER-NAME':('observation','command','special','data','database','resource','ui'),
 'MODIFIER-TIME':('command','observation','special','time'),
 'MODIFIER-TIMEOUT':('ui','command','observation','time'),
 'MODIFIER-TOLERANCE':('limits','command','observation'),
 'MODIFIER-TYPE':('ui','limits','data','database','values'),
 'MODIFIER-VALUE':('data','observation','command','database','resource','special'),
 'MODIFIER-VALUEFORMAT':('observation','command','special','data'),
 'SECTION-3-1-015':('extension','common','observation','command','special','database','resource'),
}


def component_checks(reviewed):
    assert set(reviewed)=={kind for groups in MAP.values() for kind in groups}
    assert len({r['runtime_image'] for r in reviewed.values()})==1
    assert all(r.get('passed',True) is True and all(row['passed'] is True for row in r['checks'].values()) for r in reviewed.values())
    checks={}
    for identifier,groups in MAP.items():
        for dimension in DIMENSIONS:
            dependencies=[]
            for kind in groups:
                keys=[key for key,row in reviewed[kind]['checks'].items() if row.get('dimension')==dimension]
                assert keys,kind+':'+dimension
                dependencies += [dict(report=kind,check=key) for key in keys]
            checks[PREFIX+identifier+':'+dimension]=dict(passed=True,dimension=dimension,
                contracts=[PREFIX+identifier],dependencies=dependencies,
                oracle='Every applicable service family independently validates this shared modifier, actual return/effect, rejection and recovery; the RESUME extension uses real driver hooks and nonduplicated durable command receipts.')
    return link_components(checks,reviewed)


def qualify(sequence_path,native_wheel,driver_wheel,native_pair):
    from data_aggregate_report import qualify as data_review
    from database_complete_report import qualify as database_review
    from special_complete_report import qualify as special_review
    from observation_complete_report import qualify as observation_review
    from command_complete_report import qualify as command_review
    from ui_complete_report import qualify as ui_review
    from driver_extension_review import review as extension_review
    from resource_report import qualify as resource_review
    from value_units_report import qualify as values_review
    from limit_full_report import qualify as limit_review
    from installed_provenance import verify_capture
    required=('driver-extension','common','time','resource','value-units','limit','limit-features')
    sequence,paths,raws,inputs=complete_sequence(sequence_path,required);image=sequence['image']
    for name in ('common','time'):
        verify_capture(raws[name]['runtime_sources']['integrated'],raws[name]['inputs'],raws[name].get('lf_normalized_inputs'))
    reviewed=dict(data=data_review(sequence_path),database=database_review(sequence_path,native_wheel,driver_wheel),
        special=special_review(sequence_path,native_wheel,driver_wheel),
        observation=observation_review(sequence_path,native_wheel,driver_wheel),
        command=command_review(sequence_path,native_wheel,driver_wheel),
        ui=ui_review(sequence_path,native_wheel,driver_wheel,native_pair),
        extension=extension_review(paths['driver-extension'],image,native_wheel,driver_wheel),
        common=raws['common'],time=raws['time'],resource=resource_review(raws['resource']),values=values_review(raws['value-units']),
        limits=limit_review(paths['limit-features'],paths['limit'],sequence_path,sequence['source_commit'],image,native_wheel,driver_wheel))
    checks=component_checks(reviewed);merge_review_inputs(inputs,reviewed.values())
    for name in ('conformance/common_complete_report.py','tests/test_common_complete_mapping.py'):
        inputs[name]=sha(ROOT/name)
    # Preserve review identities and raw references without duplicating every
    # large native transcript in the shared-modifier report.
    import hashlib,json
    summaries={name:dict(passed=True,runtime_image=report['runtime_image'],
        checks_sha256=hashlib.sha256(json.dumps(report['checks'],sort_keys=True).encode()).hexdigest(),
        raw=report.get('raw'),qualified_contracts=report.get('qualified_contracts',[])) for name,report in reviewed.items()}
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,
        qualified_contracts=sorted(PREFIX+name for name in MAP),independent_reviews=summaries,
        sequence=ref(sequence_path),full_v05_accepted=False,
        scope='Seventeen remaining common language contracts across the declared original GENERIC/DSS service profile, including the documented explicit driver extension point for RESUME.')
