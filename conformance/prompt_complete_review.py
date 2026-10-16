"""Independent result and client-event oracles for native timeout behavior."""
from host_observation_review import ROOT,evidence,sha,read,ref
from prompt_complete_cases import CASES

EXPECTED={
 'empty-default:positive':[('EMPTY','','str')],
 'empty-default:boundary':[('EMPTY_LIST','','str')],
 'empty-default:failure':[{'rejected':'timeout'}],
 'empty-default:recovery':[{'rejected':'timeout'},('RECOVER_EMPTY','','str')],
 'reminder:positive':[{'value':'operator'}],
 'reminder:boundary':[{'value':'operator'}],
 'reminder:failure':[{'value':'operator'}],
 'reminder:recovery':[{'value':'operator'},('AFTER_REMINDER','','str')],
 'typed-default:positive':[('INTEGER','42','int'),('DATE','03-Apr-2006 09:52:34','TIME'),('YES','True','bool')],
 'typed-default:boundary':[('ZERO','0','int'),('FRACTION','-0.25','float'),('NO','False','bool')],
 'typed-default:failure':[{'rejected':'not-a-number'},{'rejected':'not-a-date'}],
 'typed-default:recovery':[{'rejected':'invalid'},('RECOVER_NUM','1','int'),('LEAP_DAY','29-Feb-2024 00:00:00','TIME')],
}
PROMPTS={name:count for name,count in zip(EXPECTED,(1,1,0,1,1,1,1,2,3,3,2,3))}


def inspect(name,row,transcript,results):
    assert row['dimension']==name.split(':')[1]
    assert results==row['results'] and len(results)==len(EXPECTED[name])
    for result,expected in zip(results,EXPECTED[name]):
        if isinstance(expected,dict):assert result==expected
        else:
            assert set(result)=={'label','value','type','elapsed'}
            assert (result['label'],result['value'],result['type'])==expected
            assert .25<=result['elapsed']<8
    prompts={}
    for frame in transcript:
        if frame.get('event')!='spell/prompt':continue
        body=frame['body'];identifier=body['promptId']
        assert body['procedureId']==body['ProcId']=='main#1'
        assert identifier not in prompts or prompts[identifier]==body
        prompts[identifier]=body
        manual=body['Text']=='MANUAL'
        assert body['DefaultProvided']==('False' if manual else 'True')
        assert float(body['TimeoutMicroseconds'])==(0 if name=='reminder:boundary' else 250000)
    assert prompts==row['prompts'] and len(prompts)==PROMPTS[name]
    reminders=[m['body'] for m in transcript if m.get('event')=='openbexi/promptReminder']
    required=name in ('reminder:positive','reminder:failure','reminder:recovery')
    assert reminders==row['reminders'] and len(reminders)==int(required)
    if required:
        reminder,=reminders;assert reminder['procedureId']=='main#1'
        assert prompts[reminder['promptId']]['Text']=='MANUAL'
    requests=[m for m in transcript if m.get('type')=='request' and m.get('command')=='openbexi/input']
    responses={m['request_seq']:m for m in transcript if m.get('type')=='response'}
    if name.startswith('reminder:'):
        assert len(requests)==(2 if name=='reminder:failure' else 1)
        request=requests[-1];body=request['arguments']
        assert body['text']=='operator' and prompts[body['promptId']]['Text']=='MANUAL'
        assert responses[request['seq']]['success'] is True
        if required:
            event_index=next(i for i,m in enumerate(transcript) if m.get('event')=='openbexi/promptReminder')
            assert event_index<transcript.index(request)
        if name=='reminder:failure':
            rejected=requests[0]
            assert rejected['arguments']['promptId'] not in prompts
            assert rejected['arguments']['text']=='wrong'
            assert responses[rejected['seq']]['success'] is False and row['stale_rejected'] is True
    else:assert requests==[]


def review(path,image,native_wheel,driver_wheel):
    raw,wheels=evidence(path,image,12,native_wheel,driver_wheel)
    assert raw['require_timeout_metadata'] is True and set(raw['checks'])==set(EXPECTED)
    checks={}
    for name,row in raw['checks'].items():
        directory=path.parent/name.replace(':','-')
        assert (directory/'main.py').read_text(encoding='utf-8')==CASES[name]['source']
        inspect(name,row,read(directory/'transcript.json'),read(directory/'procedure-result.json'))
        checks[name]=dict(passed=True,dimension=name.split(':')[1],contracts=[],
            oracle='Literal typed results, actual default deadlines, native timeout metadata and retained DAP prompt/answer/reminder ordering; absent defaults remain waiting and stale answers have no effect.')
    inputs=dict(raw['inputs'])
    for name in ('conformance/host_observation_review.py','conformance/prompt_complete_review.py'):
        inputs[name]=sha(ROOT/name)
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,raw=ref(path),
        composed_wheels=wheels,qualified_contracts=[],full_v05_accepted=False)
