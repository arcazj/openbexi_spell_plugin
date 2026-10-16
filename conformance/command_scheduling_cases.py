"""Independent native probes for individual command modifiers, before promotion."""
HEADER='''##########
# NAME: Individual command scheduling qualification candidate
# SPACECRAFT: GENERIC
# PYTHON VERSION: 3
##########
import json
from pathlib import Path
from spell.lang.functions import Send
from spell.lib.adapter.utctime import NOW,TIME,MINUTE
observed={'calls':[]}
def send(expect=True,**options):
    row={'options':{key:str(value) for key,value in options.items()}}
    observed['calls'].append(row)
    try:
        value=Send(command='CMD1',HandleError=False,PromptUser=False,Confirm=False,**options)
        row.update(returned=value,return_type=type(value).__name__)
    except Exception as error:
        row.update(error_type=type(error).__name__,error=str(error))
        if expect:raise
    else:
        assert expect and value is True,row
    finally:
        Path('observed.json').write_text(json.dumps(observed,indent=2),encoding='utf-8')
'''

CASES={}
def add(family,dimension,body,executions,stages):
    CASES[family+':'+dimension]=dict(dimension=dimension,source=HEADER+body+"\nPath('result.json').write_text(json.dumps({'completed':True}))\n",
        expected_executions=executions,expected_stages=stages)

for name in ('Time','ReleaseTime'):
    add(name,'positive',f"send({name}=NOW+TIME('+00:00:00.25'))",1,5)
    add(name,'boundary',f"send({name}=NOW-TIME('+00:00:01'))",1,5)
    add(name,'failure',f"send(False,{name}=TIME('+00:00:01'))",0,0)
    add(name,'recovery',f"send(False,{name}=TIME('+00:00:01'))\nsend({name}=NOW+TIME('+00:00:00.25'))",1,5)
    add(name,'encoding',f"send({name}=str(NOW+TIME('+00:00:00.25')))",1,5)
add('SendDelay','positive',"send(SendDelay=TIME('+00:00:00.25'))",1,5)
add('SendDelay','boundary',"send(SendDelay=0)",1,5)
add('SendDelay','failure',"send(False,SendDelay=-1)",0,0)
add('SendDelay','recovery',"send(False,SendDelay=-1)\nsend(SendDelay=TIME('+00:00:00.25'))",1,5)
add('SendDelay','encoding',"send(SendDelay='+00:00:00.25')",1,5)
add('LoadOnly','positive',"send(LoadOnly=True)",0,2)
add('LoadOnly','boundary',"send(LoadOnly=False)",1,5)
add('LoadOnly','failure',"send(False,LoadOnly='yes')",0,0)
add('LoadOnly','recovery',"send(False,LoadOnly='yes')\nsend(LoadOnly=True)",0,2)
add('LoadOnly','encoding',"send(LoadOnly=True,addInfo={'note':'café λ'})",0,2)
add('Timeout','positive',"send(Timeout=MINUTE)",1,5)
add('Timeout','boundary',"send(Timeout=31)",1,5)
add('Timeout','failure',"send(False,Timeout=0)",0,0)
add('Timeout','recovery',"send(False,Timeout=0)\nsend(Timeout=MINUTE)",1,5)
add('Timeout','encoding',"send(Timeout='+00:01:00')",1,5)
add('addInfo','positive',"send(addInfo={'attempt':1,'enabled':True})",1,5)
add('addInfo','boundary',"send(addInfo={})",1,5)
add('addInfo','failure',"send(False,addInfo=[])",0,0)
add('addInfo','recovery',"send(False,addInfo=[])\nsend(addInfo={'attempt':2})",1,5)
add('addInfo','encoding',"send(addInfo={'note':'café λ','nested':{'value':'遥測'}})",1,5)
