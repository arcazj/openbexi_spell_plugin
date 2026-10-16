"""Complete command language contracts after actual routing, limits and verification."""
from aggregate_support import ROOT,PREFIX,DIMENSIONS,sha,read,ref,complete_sequence,merge_review_inputs

MAP={}


def bind(names,**groups):
    for name in names:
        assert name not in MAP
        MAP[name]=groups


bind(('FUNCTION-BUILDTC','SECTION-4-4-044','SECTION-4-4-1-045','TYPE-TELECOMMANDITEM'),
     command=('*',),features=('*',),complete=('complex-send',))
bind(('KEYWORD-ARGUMENT-ARGS',),command=('*',),complete=('complex-send',),arguments=('*',))
bind(('SECTION-4-5-7-053',),command=('*',),complete=('complex-send',))
bind(('MODIFIER-BLOCK',),features=('*',),command=('*',))
bind(('MODIFIER-ADJLIMITS','EXAMPLE-076','SECTION-4-5-15-061'),
     complete=('adjust-analog','adjust-status'),verification=('*',))
bind(('EXAMPLE-075','KEYWORD-ARGUMENT-VERIFY','SECTION-4-5-14-060'),
     command=('*',),verification=('*',),timing=('*',),complete=('*',),observation=('*',))
bind(('EXAMPLE-077','SECTION-4-5-16-062'),complete=('complex-send',),verification=('*',),features=('*',))
bind(('FUNCTION-SEND','SECTION-4-5-046','SECTION-4-5-17-063'),
     command=('*',),features=('*',),verification=('*',),timing=('*',),complete=('*',),observation=('*',))
bind(('SECTION-4-6-064',),observation=('*',))


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
                    row=available[key];assert row['passed'] is True and row['dimension']==dimension
                    dependencies.append(dict(report=kind,check=key))
            checks[PREFIX+identifier+':'+dimension]=dict(passed=True,dimension=dimension,
                contracts=[PREFIX+identifier],dependencies=dependencies,
                oracle='Native argument construction, actual command packets and receipts, Group/Block/scheduled execution, composed TM verification and automatic limit effects satisfy all required clauses.')
    return checks


def qualify(sequence_path,native_wheel,driver_wheel):
    from command_display_composed_report import qualify as feature_review
    from cmd_report import qualify as command_review
    from send_verify_report import qualify as verification_review
    from timing_report import qualify as timing_review
    from send_complete_review import review as complete_review
    from child_arguments_report import qualify as arguments_review
    from observation_complete_report import qualify as observation_review
    required=('cmd','command-scheduling','command-catalog','command-group','gcs-display',
              'send-verify','send-complete','timing','child-arguments')
    sequence,paths,raws,inputs=complete_sequence(sequence_path,required)
    image,revision=sequence['image'],sequence['source_commit']
    features=feature_review({name:paths[suite] for name,suite in
        (('scheduling','command-scheduling'),('catalog','command-catalog'),
         ('group','command-group'),('display','gcs-display'))},image,revision)
    reviewed=dict(command=command_review(raws['cmd']),features=features,
        verification=verification_review(raws['send-verify']),timing=timing_review(raws['timing']),
        complete=complete_review(paths['send-complete'],None,None,None,revision,image,
            native_wheel=native_wheel,driver_wheel=driver_wheel),
        arguments=arguments_review(paths['child-arguments']),
        observation=observation_review(sequence_path,native_wheel,driver_wheel))
    assert reviewed['complete']['composed_wheels']['passed']
    checks=component_checks(reviewed)
    assert len(MAP)==19 and {PREFIX+name for name in MAP}<={r['id'] for r in read(ROOT/'conformance/inventory.json')['rows']}
    merge_review_inputs(inputs,reviewed.values())
    for name in ('conformance/command_complete_report.py','conformance/send_complete_review.py',
                 'tests/test_command_complete_mapping.py'):
        inputs[name]=sha(ROOT/name)
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,
        qualified_contracts=sorted(PREFIX+name for name in MAP),independent_reviews=reviewed,
        sequence=ref(sequence_path),raw={name:ref(path) for name,path in paths.items()},full_v05_accepted=False,
        scope='Complete BuildTC and Send contracts, original argument/verification forms and command-held execution, including literal binary argument encoding, exactly counted command executions and native Result details.')


if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser()
    for name in ('sequence','native-wheel','driver-wheel','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=qualify(args.sequence,args.native_wheel,args.driver_wheel)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,contracts=len(result['qualified_contracts']),output=str(args.output))))
