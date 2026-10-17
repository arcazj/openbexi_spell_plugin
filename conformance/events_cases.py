"""Independent expected event delivery and explicit resend boundaries."""
CASES={}
METADATA={}


def add(group, dimension, code, contracts):
    key=group+':'+dimension
    CASES[key]=code
    METADATA[key]=dict(dimension=dimension,contracts=['CMP-LRM244-'+x for x in contracts],
        oracle='Original native calls; exact client message/event journal tuples or immutable real DSS receipts with independent counts, outcomes and operation identities.')


EVENT=['EXAMPLE-110']
add('event','positive',"before=mark(); assert Event('',config=CFG) is True; assert Event('EV:info',config=CFG) is True; assert Event('EV:warning',WARNING,config=CFG) is True; assert Event('EV:error',config=dict(CFG,Severity=ERROR)) is True; verify_events(before,[('',8),('EV:info',8),('EV:warning',1),('EV:error',2)])",EVENT)
add('event','boundary',"before=mark(); text='EV:boundary:'+('caf\u00e9\\n'*3277); assert len(text)>16384; assert Event(text,WARNING,config=CFG) is True; verify_events(before,[(text,1)])",EVENT)
add('event','failure',"before=mark(); rejects(SyntaxException,lambda:Event(123,config=CFG)); rejects(SyntaxException,lambda:Event(config=CFG)); rejects(RuntimeError,lambda:Event('INVALID_SEVERITY',config=dict(CFG,Severity=19))); rejects(RuntimeError,lambda:Event('INVALID_SCOPE',config=dict(CFG,Scope=19))); verify_events(before,[])",EVENT)
add('event','recovery',"before=mark(); rejects(RuntimeError,lambda:Event('INVALID_SEVERITY',config=dict(CFG,Severity=19))); assert Event('',config=CFG) is True; assert Event('EV:recovery',config=CFG) is True; verify_events(before,[('',8),('EV:recovery',8)])",EVENT)

RESEND=['CONSTANT-ACTION-RESEND']
add('resend','positive',"assert Send(command='TC.SIMULATOR.SET_MODE',args=[['MODE','SAFE']],config=CFG); before=mark(); plan_resend('RESEND','NOMINAL'); assert Send(command='CMD1',config=dict(CFG,HandleError=True,PromptFailure=True,PromptUser=True,OnFalse=NOACTION)) is True; resend_receipts(before,1,True,True)",RESEND)
add('resend','boundary',"assert Send(command='TC.SIMULATOR.SET_MODE',args=[['MODE','SAFE']],config=CFG); before=mark(); plan_resend('RESEND'); plan_resend('RESEND','NOMINAL'); assert Send(command='CMD1',config=dict(CFG,HandleError=True,PromptFailure=True,PromptUser=True,OnFalse=NOACTION)) is True; resend_receipts(before,2,True,True)",RESEND)
add('resend','failure',"assert Send(command='TC.SIMULATOR.SET_MODE',args=[['MODE','SAFE']],config=CFG); before=mark(); plan_resend('RESEND'); plan_resend('CANCEL'); assert Send(command='CMD1',config=dict(CFG,HandleError=True,PromptFailure=True,PromptUser=True,OnFalse=NOACTION)) is False; resend_receipts(before,2,False,False)",RESEND)
add('resend','recovery',"before=mark(); plan_resend('RESEND','NOMINAL'); assert Send(command='CMD1',config=dict(CFG,HandleError=True,PromptFailure=True,PromptUser=True,OnFalse=NOACTION)) is True; resend_receipts(before,1,True,True)",RESEND)
