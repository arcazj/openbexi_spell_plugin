"""Native client/event journal and real commanded recovery oracles."""
from cmd_contracts import *


def plan_resend(answer, repair_mode=None):
    path = pathlib.Path('prompt-plans.json')
    plans = json.loads(path.read_text())
    plans.append(dict(choices=['ABORT','RESEND','SKIP','CANCEL'],answer=answer,repair_mode=repair_mode))
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(plans))
    temporary.replace(path)


def verify_events(before, expected):
    deadline = time.monotonic()+3
    while True:
        after=fixture('observe')
        native=[e['message']['fields'] for e in after['native'][len(before['native']):]
                if e.get('message',{}).get('id')=='MSG_WRITE']
        actual=[e for e in native if e.get('Text') in [row[0] for row in expected] and e.get('Scope')=='1']
        if len(actual)>=len(expected) or time.monotonic()>deadline:break
        time.sleep(.03)
    equal(len(actual),len(expected))
    severities={8:'INFO',1:'WARN',2:'ERROR'}
    for text,severity in expected:
        matches=[e for e in actual if e['Text']==text]
        equal(len(matches),1);equal(matches[0]['Level'],severities[severity])
    rows=after['event_journal'][len(before['event_journal']):]
    equal(rows,[dict(message=text,severity=severity,scope=1) for text,severity in expected])


def resend_receipts(before, failures, repaired, completed):
    after=mark();rows=after['evidence']['operations'][len(before['evidence']['operations']):]
    expected=[('CMD1','TRANSPORT','ACCEPTED'),('CMD1','LOADING','LOADED'),('CMD1','RELEASE','FAILED')]*failures
    stages=[('TRANSPORT','ACCEPTED'),('LOADING','LOADED'),('RELEASE','RELEASED'),('ACKNOWLEDGEMENT','ACKNOWLEDGED'),('ONBOARD_EXECUTION','SUCCEEDED')]
    if repaired:expected += [('TC.SIMULATOR.SET_MODE',s,v) for s,v in stages]
    if completed:expected += [('CMD1',s,v) for s,v in stages]
    equal([(r['acknowledgement']['command_name'],r['acknowledgement']['stage'],r['acknowledgement']['outcome']) for r in rows],expected)
    equal(after['state']['core']['commands_executed']-before['state']['core']['commands_executed'],int(repaired)+int(completed))
    assert all(r['ingress_delivery_count']==1 for r in rows)
    operations=[]
    for row in rows:
        operation=row['acknowledgement']['operation_id']
        if not operations or operations[-1]!=operation:operations.append(operation)
    equal(len(set(operations)),failures+int(repaired)+int(completed))
    if repaired:
        repairs=after['repairs'][len(before['repairs']):]
        equal(len(repairs),1)
        equal(repairs[0]['identity']['definition'],'fixture/mode-repair')
        equal(rows[failures*3]['acknowledgement']['execution_id'],repairs[0]['identity']['procedure'])
        assert rows[0]['acknowledgement']['execution_id'] != repairs[0]['identity']['procedure']


def run():
    checks={};namespace=dict(globals())
    for name,code in json.loads(pathlib.Path('cases.json').read_text()).items():
        temporary=pathlib.Path('current.tmp');temporary.write_text(json.dumps({'check':name}));temporary.replace('current.json')
        pathlib.Path('prompt-plans.json').write_text('[]')
        began=time.monotonic()
        try:
            fixture('feed',value=True)
            exec(compile(code,'EVENTS:'+name,'exec'),namespace,namespace)
            checks[name]={'passed':True}
        except Exception as error:
            checks[name]={'passed':False,'error':type(error).__name__+': '+str(error)}
        checks[name].update(seconds=time.monotonic()-began,source=code,
            expected_prompts=json.loads(pathlib.Path('prompt-plans.json').read_text()))
        pathlib.Path('checks.json').write_text(json.dumps(checks,indent=2)+'\n')
