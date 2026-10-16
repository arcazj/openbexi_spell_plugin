"""Unmodified native LIMIT surface probes; failures are retained counterexamples."""
HEADER = '''##########
# NAME: Remaining limit behavior baseline
# SPACECRAFT: GENERIC
# PYTHON VERSION: 3
##########
import json
from pathlib import Path
from spell.lang import functions as api
from spell.lang.constants import *
from spell.lang.modifiers import *
observed={'calls':[]}
def call(name,*args,**options):
    row={'function':name,'args':repr(args),'options':repr(options)}
    observed['calls'].append(row)
    try:
        value=getattr(api,name)(*args,HandleError=False,PromptUser=False,**options)
        row.update(returned=value,return_type=type(value).__name__)
        return value
    except Exception as error:
        row.update(error_type=type(error).__name__,error=str(error))
    finally:
        Path('observed.json').write_text(json.dumps(observed,indent=2),encoding='utf-8')
'''
CASES = {}


def add(name, body):
    CASES[name] = dict(dimension='positive', source=HEADER+body+'''
assert all('error_type' not in row for row in observed['calls']),observed
Path('result.json').write_text(json.dumps({'completed':True}))
''')


BASE = "call('SetLimits','TMparam',Definition={LoRed:10,LoYel:20,HiYel:30,HiRed:40})\n"
add('hardsoft-properties', """
call('SetLimits','TMparam',Definition={LoRed:10,LoYel:20,HiYel:30,HiRed:40,
    Hysteresis:2,Active:True,Name:'Normal definition',Algorithm:'TMparam1<TMparam2+TMparam3'})
call('GetLimits','TMparam',Select='GENERIC')
""")
add('multiple-definitions', """
call('SetLimits','TMparam',Limits={
    'ID1':{LoRed:10,LoYel:20,HiYel:30,HiRed:40,Active:True},
    'ID2':{LoRed:0,LoYel:5,HiYel:45,HiRed:50,Active:False}})
call('GetLimits','TMparam',Select=ALL)
call('GetLimits','TMparam',Select=ACTIVE)
call('GetLimits','TMparam',Select='ID2')
""")
add('inactive-definition', BASE+"call('SetLimits','TMparam',Definition={Active:False},Select='GENERIC')\ncall('GetLimits','TMparam',Select=ACTIVE)")
add('midpoint-property', BASE+"call('GetLimits','TMparam',Select='GENERIC',Value=Midpoint)\ncall('GetLimits','TMparam',Select='GENERIC',Value=Tolerance)")
add('status-definition', """
call('SetLimits','TM.CORE.MODE',Type=STATUS,Definition={Nominal:['NOMINAL'],Warning:['SAFE'],Error:['FAILED'],Ignore:[]})
call('GetLimits','TM.CORE.MODE',Select='GENERIC',Value=Nominal)
call('SetLimits','TM.CORE.MODE',Nominal=['NOMINAL','SAFE'],Select='GENERIC')
""")
add('spike-definition', "call('SetLimits','TMparam',Type=SPIKE,Definition={Delta:0.23})\ncall('GetLimits','TMparam',Select='GENERIC',Value=Delta)")
add('step-definition', "call('SetLimits','TMparam',Type=STEP,Definition={Delta:[0.23,0.30]})\ncall('GetLimits','TMparam',Select='GENERIC',Value=Delta)")
add('alarm-controls', BASE+"call('DisableAlarm','TMparam')\ncall('EnableAlarm','TMparam')")
add('adjust-analog', BASE+"call('AdjustLimits',[['TMparam',eq,3.4,{Tolerance:0.1}]])\ncall('GetLimits','TMparam',Select='GENERIC')")
add('adjust-status', "call('AdjustLimits',[['TM.CORE.MODE',eq,['NOMINAL']]])")
add('load-file', "call('LoadLimits','limits://normal')")
add('both-thresholds', BASE+"call('SetLimits','TMparam',LoBoth=10,HiBoth=40)")
