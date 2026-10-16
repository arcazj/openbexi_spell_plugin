"""Native catalog sequences and actual critical-command confirmation."""
HEADER='''##########
# NAME: Command catalog qualification candidate
# SPACECRAFT: GENERIC
# PYTHON VERSION: 3
##########
import json
from pathlib import Path
from spell.lang.functions import Send
observed={'calls':[]}
def send(expect=True,**options):
    row={'options':{key:str(value) for key,value in options.items()}}
    observed['calls'].append(row)
    try:
        value=Send(HandleError=False,PromptUser=False,Confirm=False,**options)
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
def add(family,dimension,body,executions,stages,members,prompts=()):
    CASES[family+':'+dimension]=dict(dimension=dimension,source=HEADER+body+
        "\nPath('result.json').write_text(json.dumps({'completed':True}))\n",
        expected_executions=executions,expected_stages=stages,expected_members=members,prompt_answers=list(prompts))
add('Sequence','positive',"send(sequence='SEQNAME')",3,15,['CMD1','CMD2','CMD3'])
add('Sequence','boundary',"send(sequence='SEQ.DUPLICATE')",3,15,['CMD1','CMD1','CMD2'])
add('Sequence','failure',"send(False,sequence='SEQ.UNKNOWN')",0,0,[])
add('Sequence','recovery',"send(False,sequence='SEQ.UNKNOWN')\nsend(sequence='SEQ.DUPLICATE')",3,15,['CMD1','CMD1','CMD2'])
add('Sequence','encoding',"send(sequence='SEQNAME',addInfo={'note':'café λ 遥測'})",3,15,['CMD1','CMD2','CMD3'])
add('SequenceLoadOnly','positive',"send(sequence='SEQNAME',LoadOnly=True)",0,6,['CMD1','CMD2','CMD3'])
add('ConfirmCritical','positive',"send(command='TC.SIMULATOR.RESET',ConfirmCritical=True)",1,5,['TC.SIMULATOR.RESET'],['O'])
add('ConfirmCritical','boundary',"send(command='TC.SIMULATOR.RESET',ConfirmCritical=False)",1,5,['TC.SIMULATOR.RESET'])
add('ConfirmCritical','failure',"send(False,command='TC.SIMULATOR.RESET',ConfirmCritical=True)",0,0,[],['C'])
add('ConfirmCritical','recovery',"send(False,command='TC.SIMULATOR.RESET',ConfirmCritical=True)\nsend(command='TC.SIMULATOR.RESET',ConfirmCritical=True)",1,5,['TC.SIMULATOR.RESET'],['C','O'])
add('ConfirmCritical','encoding',"send(command='TC.SIMULATOR.RESET',ConfirmCritical=True,addInfo={'note':'café λ 遥測'})",1,5,['TC.SIMULATOR.RESET'],['O'])
