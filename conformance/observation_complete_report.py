"""Close whole acquisition, verification and wait clauses from all native components."""
from aggregate_support import ROOT,PREFIX,DIMENSIONS,sha,read,ref,complete_sequence,merge_review_inputs,link_components

QUALITY=('quality','validity','freshness','availability','link')
MAP={}


def bind(names, **groups):
    for name in names:
        assert name not in MAP
        MAP[name]=groups


bind(('EXAMPLE-032',),telemetry=('minute',),obs=('timeout-forms',),timing=('gettm-wait',))
bind(('EXAMPLE-040','EXAMPLE-041','SECTION-4-3-9-039'),telemetry=('printed',),obs=('result',))
bind(('SYNTAX-VERIFY-BETWEEN',),telemetry=('between-list',),obs=('operator-bw','operator-nbw'))
bind(('SECTION-4-2-4-028',),telemetry=QUALITY,policy=('failure-policy',))
bind(('SECTION-4-2-5-029',),telemetry=QUALITY,policy=('failure-policy',))
bind(('FUNCTION-GETTM','SECTION-4-2-024'),telemetry=QUALITY+('minute',),policy=('failure-policy',),
     obs=('*',),timing=('gettm-wait',))
bind(('FUNCTION-VERIFY','SECTION-4-3-030'),telemetry=QUALITY+('printed','between-list'),
     policy=('failure-policy',),obs=('*',),timing=('verify-wait',))
bind(('EXAMPLE-080','EXAMPLE-081','SECTION-4-6-3-067'),obs=('*',),
     timing=('waitfor-wait','waitfor-delay'),controls=('*',))
bind(('FUNCTION-WAITFOR',),obs=('*',),telemetry=QUALITY+('between-list',),
     timing=('waitfor-wait','waitfor-delay'),controls=('*',),intervals=('*',),times=('*',),scheduler=('*',))
bind(('CONSTANT-LIMIT-SELECTION-ALL',),limits=('selectors','named','spike','step','round-trip'))


def component_checks(reviewed):
    assert all(r.get('passed',True) is True for r in reviewed.values())
    assert len({r['runtime_image'] for r in reviewed.values()})==1
    assert all(row['passed'] is True for r in reviewed.values() for row in r['checks'].values())
    checks={}
    for identifier,groups in MAP.items():
        for dimension in DIMENSIONS:
            dependencies=[]
            for kind,features in groups.items():
                available=reviewed[kind]['checks']
                keys=([key for key,row in available.items() if row.get('dimension')==dimension]
                      if features==('*',) else [feature+':'+dimension for feature in features])
                assert keys
                for key in keys:
                    row=available[key]
                    assert row['passed'] is True and row['dimension']==dimension
                    dependencies.append(dict(report=kind,check=key))
            checks[PREFIX+identifier+':'+dimension]=dict(passed=True,dimension=dimension,
                contracts=[PREFIX+identifier],dependencies=dependencies,
                oracle='All original native acquisition, condition, returned-detail, failure-policy and wait components required by this clause pass on the same installed image.')
    return link_components(checks,reviewed)


def qualify(sequence_path,native_wheel,driver_wheel):
    from telemetry_features_review import review as telemetry_review
    from telemetry_policy_review import review as policy_review
    from obs_report import qualify as obs_review
    from timing_report import qualify as timing_review
    from wait_control_report import qualify as control_review
    from wait_interval_report import qualify as interval_review
    from wait_time_report import qualify as time_review
    from scheduler_report import qualify as scheduler_review
    from limit_full_report import qualify as limit_review
    required=('telemetry-features','telemetry-policy','obs','timing','wait-controls',
              'wait-intervals','wait-time','scheduler','limit-features','limit')
    sequence,paths,raws,inputs=complete_sequence(sequence_path,required)
    image,revision=sequence['image'],sequence['source_commit']
    reviewed=dict(
        telemetry=telemetry_review(paths['telemetry-features'],None,None,revision,image,native_wheel,driver_wheel),
        policy=policy_review(paths['telemetry-policy'],None,None,revision,image,native_wheel,driver_wheel),
        obs=obs_review(raws['obs']),timing=timing_review(raws['timing']),
        controls=control_review(paths['wait-controls'],image),intervals=interval_review(paths['wait-intervals'],image),
        times=time_review(paths['wait-time'],image),scheduler=scheduler_review(raws['scheduler']),
        limits=limit_review(paths['limit-features'],paths['limit'],sequence_path,revision,image,native_wheel,driver_wheel))
    assert all(reviewed[name]['composed_wheels']['passed'] for name in ('telemetry','policy'))
    checks=component_checks(reviewed)
    assert len(MAP)==16 and {PREFIX+name for name in MAP}<={r['id'] for r in read(ROOT/'conformance/inventory.json')['rows']}
    merge_review_inputs(inputs,reviewed.values())
    for name in ('conformance/observation_complete_report.py','conformance/telemetry_features_review.py',
                 'conformance/telemetry_policy_review.py','tests/test_observation_complete_mapping.py'):
        inputs[name]=sha(ROOT/name)
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,
        qualified_contracts=sorted(PREFIX+name for name in MAP),independent_reviews=reviewed,
        sequence=ref(sequence_path),raw={name:ref(path) for name,path in paths.items()},full_v05_accepted=False,
        manual_decisions={'ALL':'The constant selects all limit definitions. Uppercase ALL in the p44/p94 prose is ordinary English, not another function argument.'},
        scope='Complete GetTM, Verify and WaitFor language contracts in the declared simulator profile, including real acquisition faults, native prompt actions, one-minute acquisition, printed result details, inclusive/exclusive bounds and native interrupted waits.')


if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser()
    for name in ('sequence','native-wheel','driver-wheel','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=qualify(args.sequence,args.native_wheel,args.driver_wheel)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,contracts=len(result['qualified_contracts']),output=str(args.output))))
