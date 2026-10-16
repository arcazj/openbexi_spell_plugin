"""Reject altered native prompt results and visible-child client observations.

These are structural fixtures, not native qualification evidence. Native
qualification additionally binds actual files, transcripts and wheel RECORDs.
"""
from copy import deepcopy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'conformance'))
import prompt_complete_review as prompt
import child_visibility_review as child


def prompt_fixture(name):
    results=[dict(item) if isinstance(item,dict) else dict(label=item[0],value=item[1],type=item[2],elapsed=.3)
        for item in prompt.EXPECTED[name]]
    labels=[item[0] if isinstance(item,tuple) else 'MANUAL' if 'value' in item else 'INVALID_DEFAULT'
        for item in prompt.EXPECTED[name] if not isinstance(item,dict) or item.get('rejected')!='timeout']
    prompts={str(i):dict(promptId=str(i),ProcId='main#1',procedureId='main#1',Text=label,
        DefaultProvided='False' if label=='MANUAL' else 'True',
        TimeoutMicroseconds='0' if name=='reminder:boundary' else '250000') for i,label in enumerate(labels,1)}
    transcript=[dict(type='event',event='spell/prompt',body=body) for body in prompts.values()]
    reminders=[]
    if name=='reminder:failure':
        transcript += [dict(type='request',seq=10,command='openbexi/input',arguments=dict(promptId='invalid',text='wrong')),
            dict(type='response',request_seq=10,success=False)]
    if name in ('reminder:positive','reminder:failure','reminder:recovery'):
        reminders=[dict(promptId='1',procedureId='main#1')]
        transcript.append(dict(type='event',event='openbexi/promptReminder',body=reminders[0]))
    if name.startswith('reminder:'):
        transcript += [dict(type='request',seq=11,command='openbexi/input',arguments=dict(promptId='1',text='operator')),
            dict(type='response',request_seq=11,success=True)]
    row=dict(dimension=name.split(':')[1],results=results,prompts=prompts,reminders=reminders,stale_rejected=True)
    return row,transcript,results


@pytest.mark.parametrize('name',list(prompt.EXPECTED))
def test_prompt_oracle_covers_all_dimensions(name):
    prompt.inspect(name,*prompt_fixture(name))


@pytest.mark.parametrize('defect',['value','type','elapsed','metadata','repeated-reminder','unscoped-answer','stale-success'])
def test_prompt_review_rejects_forged_native_behavior(defect):
    name='reminder:failure' if defect in ('repeated-reminder','unscoped-answer','stale-success') else 'empty-default:positive'
    row,transcript,results=prompt_fixture(name)
    if defect=='value':results[0]['value']='unexpected'
    elif defect=='type':results[0]['type']='NoneType'
    elif defect=='elapsed':results[0]['elapsed']=0
    elif defect=='metadata':row['prompts']['1']['DefaultProvided']='False'
    elif defect=='repeated-reminder':transcript.insert(-2,deepcopy(next(m for m in transcript if m.get('event')=='openbexi/promptReminder')))
    elif defect=='unscoped-answer':transcript[-2]['arguments']['promptId']='unknown'
    else:next(m for m in transcript if m.get('request_seq')==10)['success']=True
    with pytest.raises((AssertionError,KeyError)):prompt.inspect(name,row,transcript,results)


def child_fixture(dimension):
    spec=child.CASES[dimension]
    results={'parent.json':spec['expected'],**{name:dict(instance=name[:-5]+'#0',parent='main#1') for name in spec['results']}}
    console=[]
    for name in spec['shown']:
        identity=results[name[:-3]+'.json']['instance']
        console += [dict(category='console',source={'path':'/project/'+name},output=value)
            for value in ('=== SPELL child '+identity+' ===\n',spec['files'][name],'=== End child source ===\n')]
    row=dict(dimension=dimension,results=results,console=console)
    transcript=[dict(event='output',body=body) for body in console]
    return row,transcript,dict(spec['files']),results


@pytest.mark.parametrize('dimension',list(child.EXPECTED))
def test_child_oracle_covers_all_dimensions(dimension):
    child.inspect(*child_fixture(dimension),dimension)


@pytest.mark.parametrize('defect',['code','identity','hidden-leak','duplicate','parent'])
def test_child_review_rejects_wrong_source_or_visibility(defect):
    dimension='boundary' if defect=='hidden-leak' else 'positive'
    row,transcript,files,results=child_fixture(dimension)
    if defect=='code':row['console'][1]['output']='# wrong source\n'
    elif defect=='identity':row['console'][0]['output']='=== SPELL child other#0 ===\n'
    elif defect=='duplicate':transcript.extend(deepcopy(transcript))
    elif defect=='parent':results['child.json']['parent']='other#1'
    else:
        body=dict(category='console',source={'path':'/project/hidden.py'},output=files['hidden.py'])
        row['console'].append(body);transcript.append(dict(event='output',body=body))
    with pytest.raises((AssertionError,KeyError)):child.inspect(row,transcript,files,results,dimension)
