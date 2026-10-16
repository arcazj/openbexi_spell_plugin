"""Native PROC ownership, initial-argument and procedure-lifetime controls."""
import textwrap

VALUES = {
    'positive': {'A': 1, 'B': 2},
    'boundary': {},
    'failure': {'zero': 0, 'false': False, 'text': ''},
    'recovery': {'text': 'caf\u00e9 \u03bb', 'negative': -7},
}
CASES = {}

PATHS=textwrap.dedent('''\
    from spell.lang.constants import INPUT_DATA,OUTPUT_DATA
    input_path=Path(PROC[INPUT_DATA])
    output_path=Path(PROC[OUTPUT_DATA])
    assert str(input_path)==plan['input'] and str(output_path)==plan['output']
    assert input_path!=output_path and input_path.is_dir() and output_path.is_dir()
    path_errors=[]
    try:
        (input_path/'missing-input.txt').read_text()
    except FileNotFoundError:
        path_errors.append('missing-input')
    assert path_errors==['missing-input']
    assert (input_path/'input.txt').read_text()==plan['content']
    (output_path/(PROC['NAME'].replace('#','-')+'.txt')).write_text(plan['content'])
    assert (output_path/(PROC['NAME'].replace('#','-')+'.txt')).read_text()==plan['content']
''')

LIFETIME = textwrap.dedent('''\
    import json
    from pathlib import Path
    from spell.runtime import PROC,ARGS,Step
    plan=json.loads(Path('plan.json').read_text())
    previous=json.loads(Path('runs.json').read_text()) if Path('runs.json').exists() else []
    phase=len(previous)+1
    initial=json.loads(json.dumps(PROC))
    __PATH_CHECKS__
    assert 'PRIVATE_VALUE' not in PROC,initial
    assert isinstance(PROC['ARGS'],dict) and PROC['ARGS']==plan['arguments'],initial
    assert all(type(PROC['ARGS'][key]) is type(value) for key,value in plan['arguments'].items())
    assert PROC['NAME']=='main#1' and PROC['PARENT']==''
    assert PROC['STEP'] is None and PROC['PREV_STEP'] is None
    rejected=[]
    try:
        PROC[[]]
    except TypeError:
        rejected.append('unhashable')
    try:
        PROC['ABSENT-METADATA-KEY']
    except KeyError:
        rejected.append('missing')
    assert rejected==['unhashable','missing']
    PROC['PRIVATE_VALUE']={'phase':phase}
    Step('LIFETIME','Procedure lifetime control')
    # Changing the public metadata dictionary must not change native ARGS, or
    # the initial-argument snapshot used by a later reload.
    PROC['ARGS']['PRIVATE_ARGUMENT']=phase
    assert 'PRIVATE_ARGUMENT' not in ARGS.keys()
    row={'phase':phase,'initial':initial,'rejected':rejected,
         'evaluations':int(Path('evaluations.txt').read_text())}
    previous.append(row)
    Path('runs.json').write_text(json.dumps(previous))
    if plan['dimension']=='failure' and phase==1:
        raise RuntimeError('EXPECTED_PROC_LIFETIME_FAILURE')
    if plan['dimension']=='recovery' and phase in (1,2):
        raise RuntimeError('EXPECTED_PROC_LIFETIME_FAILURE')
    Path('completed.txt').write_text(str(phase))
''').replace('__PATH_CHECKS__',PATHS.rstrip())

CHILD = textwrap.dedent('''\
    import json
    from pathlib import Path
    from spell.runtime import PROC,ARGS,Step
    from spell.lang.functions import DisplayStep
    plan=json.loads(Path('plan.json').read_text())
    initial=dict(PROC)
    __PATH_CHECKS__
    assert 'PRIVATE_VALUE' not in PROC
    assert PROC['ARGS']==plan['arguments'] and isinstance(PROC['ARGS'],dict)
    assert all(type(PROC['ARGS'][key]) is type(value) for key,value in plan['arguments'].items())
    assert PROC['NAME'].split('#',1)[0]=='child' and PROC['PARENT']=='main#1',initial
    assert PROC['STEP'] is None and PROC['PREV_STEP'] is None
    rejected=[]
    try:
        PROC['ABSENT-METADATA-KEY']
    except KeyError:
        rejected.append('missing')
    try:
        PROC[[]]
    except TypeError:
        rejected.append('unhashable')
    assert rejected==['missing','unhashable']
    PROC['PRIVATE_VALUE']={'owner':'child'}
    Step('CHILD','Child metadata')
    first={'step':PROC['STEP'],'previous':PROC['PREV_STEP']}
    DisplayStep('DONE','Child done')
    last={'step':PROC['STEP'],'previous':PROC['PREV_STEP']}
    assert first=={'step':['CHILD','Child metadata'],'previous':None},first
    assert last=={'step':['DONE','Child done'],'previous':['CHILD','Child metadata']},last
    assert {key:ARGS[key] for key in ARGS.keys()}==plan['arguments']
    Path('child-result.json').write_text(json.dumps({'initial':initial,'first':first,
        'last':last,'custom':PROC['PRIVATE_VALUE'],'rejected':rejected}))
''').replace('__PATH_CHECKS__',PATHS.rstrip())

for dimension, arguments in VALUES.items():
    for operation in ('reload','reopen'):
        CASES[operation+':'+dimension] = dict(dimension=dimension, arguments=arguments,
            source=LIFETIME, operation=operation, rounds=3 if dimension=='recovery' else 2)
    parent = textwrap.dedent('''\
        import json
        from pathlib import Path
        from spell.runtime import PROC
        from spell.lang.functions import StartProc
        plan=json.loads(Path('plan.json').read_text())
        __PATH_CHECKS__
        assert PROC['NAME']=='main#1' and PROC['PARENT']==''
        assert PROC['ARGS']=={} and isinstance(PROC['ARGS'],dict)
        PROC['PRIVATE_VALUE']={'owner':'parent'}
        assert StartProc('child',args=[[key,value] for key,value in plan['arguments'].items()],HandleError=False) is True
        assert PROC['PRIVATE_VALUE']=={'owner':'parent'}
        assert PROC['ARGS']=={} and PROC['STEP'] is None and PROC['PREV_STEP'] is None
        Path('parent-result.json').write_text(json.dumps({'initial':dict(PROC),'returned':True}))
    ''').replace('__PATH_CHECKS__',PATHS.rstrip())
    CASES['child:'+dimension]=dict(dimension=dimension,arguments=arguments,source=parent,
        child=CHILD,operation='child',rounds=1)

for name,spec in CASES.items():
    compile(spec['source'],name,'exec')
    if 'child' in spec:compile(spec['child'],name+':child','exec')
