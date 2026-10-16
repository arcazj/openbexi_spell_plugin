"""Baseline native PROC observations against the dictionary contract on LRM p81."""
import textwrap

CASES={}
for dimension,arguments in (
    ('positive',{'A':1,'B':2}),
    ('boundary',{'zero':0,'false':False,'text':''}),
    ('failure',{}),
    ('recovery',{'text':'caf\u00e9 \u03bb','negative':-7}),
):
    source=textwrap.dedent('''\
        import json
        from pathlib import Path
        from spell.runtime import PROC,Step
        from spell.lang.functions import DisplayStep
        from spell.lang.constants import INPUT_DATA,OUTPUT_DATA
        plan=json.loads(Path('plan.json').read_text())
        observed={'initial':dict(PROC),'args_type':type(PROC['ARGS']).__name__}
        PROC['VAR']={'A':[1,False,'caf\u00e9']}
        assert PROC['VAR']=={'A':[1,False,'caf\u00e9']}
        observed['custom']=PROC['VAR']
        errors=[]
        try:
            PROC[[]]
        except TypeError:
            errors.append('unhashable')
        try:
            PROC['ABSENT-METADATA-KEY']
        except KeyError:
            errors.append('missing')
        assert errors==['unhashable','missing']
        Step('FIRST','Initial step')
        observed['first']={'step':PROC['STEP'],'previous':PROC['PREV_STEP']}
        DisplayStep('SECOND','Displayed step')
        observed['second']={'step':PROC['STEP'],'previous':PROC['PREV_STEP']}
        PROC['VAR']=42
        assert PROC['VAR']==42
        observed['recovery']=PROC['VAR']
        observed['errors']=errors
        Path('observed.json').write_text(json.dumps(observed))
        assert isinstance(PROC['ARGS'],dict),('LRM p81 requires a dictionary',type(PROC['ARGS']).__name__,repr(PROC['ARGS']))
        assert PROC['ARGS']==plan['arguments']
        assert all(type(PROC['ARGS'][key]) is type(value) for key,value in plan['arguments'].items())
        assert PROC['NAME']=='main#1'
        assert PROC['PARENT']==''
        assert observed['initial']['STEP'] is None and observed['initial']['PREV_STEP'] is None
        assert observed['first']=={'step':['FIRST','Initial step'],'previous':None}
        assert observed['second']=={'step':['SECOND','Displayed step'],'previous':['FIRST','Initial step']}
        assert isinstance(PROC[INPUT_DATA],str) and PROC[INPUT_DATA]
        assert isinstance(PROC[OUTPUT_DATA],str) and PROC[OUTPUT_DATA]
        Path('result.json').write_text(json.dumps({'metadata':True}))
    ''')
    compile(source,'proc:'+dimension,'exec')
    CASES['proc:'+dimension]=dict(source=source,dimension=dimension,arguments=arguments,waiting=False)
