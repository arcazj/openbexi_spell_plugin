"""Four native counterexample probes; these do not qualify any inventory row."""
HEADER='''##########
# NAME: Display compatibility baseline
# SPACECRAFT: GENERIC
# PYTHON VERSION: 3
##########
import json
from pathlib import Path
import spell.lang.functions as functions
import spell.lang.constants as constants
import spell.lang.modifiers as modifiers
from spell.lang.modifiers import OnFailure,PromptUser,HandleError,Host,Time,Format,Printer
from spell.lang.constants import CANCEL
from spell.lib.adapter.utctime import TIME
observed={'calls':[]}
def call(name,**options):
    row={'function':name,'options':{k:str(v) for k,v in options.items()}}
    observed['calls'].append(row)
    try:
        value=getattr(functions,name)('DSS_TELEMETRY',**{OnFailure:CANCEL,PromptUser:False,HandleError:False,**options})
        row.update(returned=value,return_type=type(value).__name__)
    except Exception as error:
        row.update(error_type=type(error).__name__,error=str(error))
    return row.get('returned') is True
'''

BODIES={
    'api-surface':'''observed['functions']={name:callable(getattr(functions,name,None)) for name in ('OpenWorkspace','CloseWorkspace')}
observed['formats']={name:getattr(constants,name,None) for name in ('PS','VECTOR')}
observed['modifiers']={name:getattr(modifiers,name,None) for name in ('Monitor','Reuse')}
ok=all(observed['functions'].values()) and all(observed['formats'].values()) and all(observed['modifiers'].values())
''',
    'display-lifecycle':'''opened=call('OpenDisplay')
closed=call('CloseDisplay')
ok=opened and closed
''',
    'display-options':'''outcomes=[]
for options in ({Host:'DSS'},{'Monitor':1},{'Reuse':True},
                {Host:'DSS','Monitor':1,'Reuse':False}):
    outcomes.append(call('OpenDisplay',**options))
    outcomes.append(call('CloseDisplay',**{Host:'DSS'}))
ok=all(outcomes)
''',
    'print-vector':'''opened=call('OpenDisplay')
vector=call('PrintDisplay',**{Format:'VECTOR'})
postscript=call('PrintDisplay',**{Format:'PS'})
printer=call('PrintDisplay',**{Printer:'DSS_REPORTS'})
closed=call('CloseDisplay')
ok=opened and vector and postscript and printer and closed
''',
}

CASES={name:dict(dimension='positive',source=HEADER+body+'''
Path('observed.json').write_text(json.dumps(observed,indent=2),encoding='utf-8')
assert ok, observed
Path('result.json').write_text(json.dumps({'completed':True}),encoding='utf-8')
''') for name,body in BODIES.items()}
