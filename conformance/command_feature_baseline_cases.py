"""Observe unimplemented command paths independently, without coverage promotion."""
HEADER='''##########
# NAME: Command feature baseline
# SPACECRAFT: GENERIC
# PYTHON VERSION: 3
##########
import json
from pathlib import Path
from spell.lang.functions import Send
import spell.lang.modifiers as modifiers
from spell.lib.adapter.utctime import NOW, TIME, MINUTE
observed={'calls':[]}
def send(**options):
    row={'options':{key:str(value) for key,value in options.items()}}
    observed['calls'].append(row)
    try:
        value=Send(HandleError=False,PromptUser=False,Confirm=False,**options)
        row.update(returned=value,return_type=type(value).__name__)
    except Exception as error:
        row.update(error_type=type(error).__name__,error=str(error))
    return row.get('returned') is True
'''

BODIES={
    'api-surface':'''observed['modifiers']={name:getattr(modifiers,name,None) for name in ('Group','LoadOnly')}
ok=all(observed['modifiers'].values())
''',
    'scheduling':'''outcomes=[]
outcomes.append(send(command='CMD1',Time=NOW+TIME('+00:00:00.25')))
outcomes.append(send(command='CMD1',ReleaseTime=NOW+TIME('+00:00:00.25')))
outcomes.append(send(command='CMD1',SendDelay=TIME('+00:00:00.25')))
ok=all(outcomes)
''',
    'load-only':'''ok=send(command='CMD1',LoadOnly=True)
''',
    'grouped-blocked':'''grouped=send(group=['CMD1','CMD3'],Group=True)
blocked=send(group=['CMD1','CMD3'],Block=True)
ok=grouped and blocked
''',
    'sequence':'''first=send(sequence='SEQNAME')
second=send(sequence='SEQ.DUPLICATE')
ok=first and second
''',
    'timeout':'''ok=send(command='CMD1',Timeout=MINUTE)
''',
    'critical':'''ok=send(command='TC.SIMULATOR.RESET',ConfirmCritical=False)
''',
    'additional-information':'''ok=send(command='CMD1',addInfo={'note':'café λ','attempt':1})
''',
}

CASES={name:dict(dimension='positive',source=HEADER+body+'''
Path('observed.json').write_text(json.dumps(observed,indent=2),encoding='utf-8')
assert ok, observed
Path('result.json').write_text(json.dumps({'completed':True}),encoding='utf-8')
''') for name,body in BODIES.items()}
