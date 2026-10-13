"""Independent original command behavior and exact binary-effect oracles."""
CASES = {}
METADATA = {}


def add(group, dimension, code, contracts=()):
    key = group + ':' + dimension
    CASES[key] = code
    METADATA[key] = dict(dimension=dimension, contracts=['CMP-LRM244-' + c for c in contracts],
                        oracle='Original native TC item/helper plus real DSS immutable binary stage receipts and independent expected state; no command function or response replacement.')


add('build-basic','positive',"before=mark(); item=BuildTC('CMD1',config=CFG); assert isinstance(item,TcItemClass); equal(item.name(),'CMD1'); equal(item._getParams(),[]); effects(before,[])")
add('build-basic','boundary',"before=mark(); first=BuildTC('CMD1',config=CFG); second=BuildTC('CMD2',config=CFG); equal(first.name(),'CMD1'); equal(second.name(),'CMD2'); effects(before,[])")
add('build-basic','failure',"before=mark(); rejects(DriverException,lambda:BuildTC('NO_SUCH_COMMAND',config=CFG)); effects(before,[])")
add('build-basic','recovery',"before=mark(); item=BuildTC('CMD1',config=CFG); assert Send(command=item,config=CFG) is True; effects(before,['CMD1'])")

add('send-name','positive',"before=mark(); assert Send(command='CMD1',config=CFG) is True; effects(before,['CMD1']); equal(mark()['state']['payload']['enabled'],True)")
add('send-name','boundary',"before=mark(); assert Send(command='CMD2',config=CFG) is True; effects(before,['CMD2']); equal(mark()['state']['payload']['enabled'],False)")
add('send-name','failure',"before=mark(); rejects(SyntaxException,lambda:Send('CMD1',config=CFG)); rejects(DriverException,lambda:Send(command='NO_SUCH_COMMAND',config=CFG)); effects(before,[])")
add('send-name','recovery',"before=mark(); assert Send(command='CMD1',config=CFG) is True; effects(before,['CMD1'])")

for radix, encoded in [('DEC','255'),('HEX','0xFF'),('OCT','0o377'),('BIN','0b11111111')]:
    add('radix-'+radix,'positive',f"before=mark(); item=BuildTC('CMDNAME',args=[['ARG2',255,{{Radix:{radix},ValueType:LONG}}]],config=CFG); assert Send(command=item,config=CFG) is True; rows=effects(before,['CMDNAME']); equal(mark()['state']['core']['last_command_arguments'][0]['encoded'],{encoded!r})")
    add('radix-'+radix,'boundary',f"before=mark(); assert Send(command='CMDNAME',args=[['ARG2',0,{{Radix:{radix},ValueType:LONG}}]],config=CFG) is True; effects(before,['CMDNAME']); equal(mark()['state']['core']['last_command_arguments'][0]['value'],0)")
    add('radix-'+radix,'failure',f"before=mark(); rejects(DriverException,lambda:Send(command='CMDNAME',args=[['ARG2',65536,{{Radix:{radix},ValueType:LONG}}]],config=CFG)); effects(before,[])")
    add('radix-'+radix,'recovery',f"before=mark(); assert Send(command='CMDNAME',args=[['ARG2',65535,{{Radix:{radix},ValueType:LONG}}]],config=CFG) is True; effects(before,['CMDNAME']); equal(mark()['state']['core']['last_command_arguments'][0]['value'],65535)")

add('group-names','positive',"before=mark(); assert Send(group=['CMD1','CMD2','CMD3'],config=CFG) is True; effects(before,['CMD1','CMD2','CMD3']); equal(mark()['state']['payload']['enabled'],False)")
add('group-names','boundary',"before=mark(); assert Send(group=['CMD1'],config=CFG) is True; effects(before,['CMD1'])")
add('group-names','failure',"before=mark(); rejects(SyntaxException,lambda:Send(group='CMD1',config=CFG)); rejects(SyntaxException,lambda:Send(group=['CMD1'],args=[['ARG1',1]],config=CFG)); effects(before,[])")
add('group-names','recovery',"before=mark(); assert Send(group=['CMD2','CMD1'],config=CFG) is True; effects(before,['CMD2','CMD1'])")

add('group-items','positive',"before=mark(); one=BuildTC('CMDNAME',args=[['ARG1',1.25]],config=CFG); two=BuildTC('CMDNAME',args=[['ARG1',2.5]],config=CFG); assert Send(group=[one,two],config=CFG) is True; effects(before,['CMDNAME','CMDNAME']); equal(mark()['state']['payload']['setpoint_milli'],2500)")
add('group-items','boundary',"before=mark(); one=BuildTC('CMDNAME',args=[['ARG1',0.0]],config=CFG); assert Send(group=[one],config=CFG) is True; effects(before,['CMDNAME']); equal(mark()['state']['payload']['setpoint_milli'],0)")
add('group-items','failure',"before=mark(); rejects(SyntaxException,lambda:Send(group=[42],config=CFG)); effects(before,[])")
add('group-items','recovery',"before=mark(); one=BuildTC('CMDNAME',args=[['ARG1',-1.5]],config=CFG); assert Send(group=[one],config=CFG) is True; effects(before,['CMDNAME']); equal(mark()['state']['payload']['setpoint_milli'],-1500)")

add('malformed-argument','failure',"before=mark(); rejects(SyntaxException,lambda:BuildTC('CMDNAME',args=[['ARG1']],config=CFG)); effects(before,[])")
add('unsupported-block','failure',"before=mark(); rejects(DriverException,lambda:Send(group=[BuildTC('CMD1',config=CFG),BuildTC('CMD2',config=CFG)],config=dict(CFG,Block=True))); effects(before,[])")

add('group-empty','failure',"before=mark(); rejects(SyntaxException,lambda:Send(group=[],config=CFG)); effects(before,[])")
add('partial-group','failure',"""
assert Send(command='TC.SIMULATOR.SET_MODE',args=[['MODE','SAFE']],config=CFG)
before=mark()
assert Send(group=['CMD2','CMD1','CMD3'],config=dict(CFG,HandleError=True,PromptFailure=False,OnFailure=CANCEL,OnFalse=NOACTION)) is False
after=mark(); rows=after['evidence']['operations'][len(before['evidence']['operations']):]
equal([r['acknowledgement']['command_name'] for r in rows],['CMD2']*5+['CMD1']*3)
equal(rows[-1]['acknowledgement']['outcome'],'FAILED')
equal(after['state']['core']['commands_executed']-before['state']['core']['commands_executed'],1)
assert all(r['ingress_delivery_count']==1 for r in rows)
""")
add('partial-group','recovery',"before=mark(); assert Send(command='TC.SIMULATOR.SET_MODE',args=[['MODE','NOMINAL']],config=CFG); assert Send(group=['CMD1','CMD2'],config=CFG); effects(before,['TC.SIMULATOR.SET_MODE','CMD1','CMD2'])")
add('failed-command-policy','failure',"""
assert Send(command='TC.SIMULATOR.SET_MODE',args=[['MODE','SAFE']],config=CFG)
before=mark()
plan_prompt(['ABORT','RESEND','SKIP','CANCEL'],'CANCEL')
assert Send(command='CMD1',config=dict(CFG,HandleError=True,PromptUser=True,PromptFailure=True,OnFalse=NOACTION)) is False
after=mark();rows=after['evidence']['operations'][len(before['evidence']['operations']):]
equal(len(rows),3);equal(rows[-1]['acknowledgement']['outcome'],'FAILED')
equal(after['state']['core']['commands_executed'],before['state']['core']['commands_executed'])
""")
add('failed-command-policy','recovery',"before=mark(); assert Send(command='TC.SIMULATOR.SET_MODE',args=[['MODE','NOMINAL']],config=CFG); assert Send(command='CMD1',config=CFG); effects(before,['TC.SIMULATOR.SET_MODE','CMD1'])")

add('confirm','positive',"before=mark(); plan_prompt(['O','C'],'O',raw_codes=True,contains=['CMD1']); assert Send(command='CMD1',config=dict(CFG,Confirm=True)); effects(before,['CMD1'])")
add('confirm','boundary',"before=mark(); assert Send(command='CMD2',config=CFG); effects(before,['CMD2'])")
add('confirm','failure',"before=mark(); plan_prompt(['O','C'],'C',raw_codes=True,contains=['ARG1','1.25']); assert Send(command='CMDNAME',args=[['ARG1',1.25]],config=dict(CFG,Confirm=True)) is False; effects(before,[])")
add('confirm','recovery',"before=mark(); plan_prompt(['O','C'],'O',raw_codes=True,contains=['ARG1','2.5']); assert Send(command='CMDNAME',args=[['ARG1',2.5]],config=dict(CFG,Confirm=True)); effects(before,['CMDNAME']); equal(mark()['state']['payload']['setpoint_milli'],2500)")

add('send-item','positive',"before=mark(); item=BuildTC('CMD1',config=CFG); assert Send(command=item,config=CFG) is True; effects(before,['CMD1'])")
add('send-item','boundary',"before=mark(); item=BuildTC('CMD2',config=CFG); assert Send(command=item,config=CFG) is True; assert Send(command=item,config=CFG) is True; effects(before,['CMD2','CMD2'])")
add('send-item','failure',"before=mark(); rejects(SyntaxException,lambda:Send(command=[BuildTC('CMD1',config=CFG)],config=CFG)); effects(before,[])")
add('send-item','recovery',"before=mark(); assert Send(command=BuildTC('CMD1',config=CFG),config=CFG) is True; effects(before,['CMD1'])")

add('mixed-arguments','positive',"before=mark(); item=BuildTC('CMDNAME',args=[['ARG1',1.25],['ARG2',0xFF,{Radix:HEX}]],config=CFG); equal([p.name for p in item._getParams()],['ARG1','ARG2']); assert Send(command=item,config=CFG); effects(before,['CMDNAME']); equal(mark()['state']['payload']['setpoint_milli'],1250); equal(mark()['state']['core']['last_command_arguments'][1]['encoded'],'0xFF')")
add('mixed-arguments','boundary',"before=mark(); assert Send(command='CMDNAME',args=[['ARG1',-1000000.0],['ARG2',0,{Radix:DEC,ValueFormat:RAW}]],config=CFG); effects(before,['CMDNAME']); equal(mark()['state']['payload']['setpoint_milli'],-1000000000); equal(mark()['state']['core']['last_command_arguments'][1]['value_format'],'RAW')")
add('mixed-arguments','failure',"before=mark(); rejects(SyntaxException,lambda:BuildTC('CMDNAME',args=[['ARG1']],config=CFG)); rejects(SyntaxException,lambda:BuildTC('CMDNAME',args=[['ARG1',1.25,'bad']],config=CFG)); rejects(SyntaxException,lambda:Send(command='CMDNAME',args=[['ARG1',1.25,{},42]],config=CFG)); rejects(DriverException,lambda:Send(command='CMDNAME',args=[['ARG1',1000000.1]],config=CFG)); effects(before,[])")
add('mixed-arguments','recovery',"before=mark(); assert Send(command='CMDNAME',args=[['ARG1',1000000.0],['ARG2',65535,{Radix:HEX,ValueFormat:ENG}]],config=CFG); effects(before,['CMDNAME']); equal(mark()['state']['payload']['setpoint_milli'],1000000000); equal(mark()['state']['core']['last_command_arguments'][1]['encoded'],'0xFFFF')")

add('group-failure-prompt','failure',"""
assert Send(command='TC.SIMULATOR.SET_MODE',args=[['MODE','SAFE']],config=CFG)
before=mark();plan_prompt(['ABORT','RESEND','SKIP','CANCEL'],'CANCEL',contains=['whole command group'])
assert Send(group=['CMD2','CMD1','CMD3'],config=dict(CFG,HandleError=True,PromptUser=True,PromptFailure=True,OnFalse=NOACTION)) is False
after=mark();rows=after['evidence']['operations'][len(before['evidence']['operations']):]
equal([r['acknowledgement']['command_name'] for r in rows],['CMD2']*5+['CMD1']*3)
equal(rows[-1]['acknowledgement']['outcome'],'FAILED');equal(after['state']['core']['commands_executed']-before['state']['core']['commands_executed'],1)
assert all(r['ingress_delivery_count']==1 for r in rows)
""")
add('group-failure-prompt','recovery',"before=mark(); assert Send(command='TC.SIMULATOR.SET_MODE',args=[['MODE','NOMINAL']],config=CFG); assert Send(group=['CMD1','CMD2','CMD3'],config=CFG); effects(before,['TC.SIMULATOR.SET_MODE','CMD1','CMD2','CMD3'])")

# Only these bounded manual rows are eligible; a rejected unsupported modifier
# never qualifies its support row. Every selected check still has an actual oracle.
GROUP_ROWS = {
    'build-basic': ['EXAMPLE-057'],
    'send-name': ['EXAMPLE-060','KEYWORD-ARGUMENT-COMMAND','SECTION-4-5-1-047'],
    'send-item': ['EXAMPLE-060','KEYWORD-ARGUMENT-COMMAND','SECTION-4-5-1-047'],
    'mixed-arguments': ['EXAMPLE-058','EXAMPLE-059','EXAMPLE-066','SYNTAX-COMMAND-ARGUMENT'],
    'group-names': ['EXAMPLE-068','KEYWORD-ARGUMENT-GROUP','SYNTAX-COMMAND-SEQUENCE','SECTION-4-5-9-055'],
    'group-items': ['EXAMPLE-069'],
    'partial-group': ['EXAMPLE-068','EXAMPLE-069','KEYWORD-ARGUMENT-GROUP','SYNTAX-COMMAND-SEQUENCE','SECTION-4-5-9-055'],
    'group-failure-prompt': ['EXAMPLE-068','EXAMPLE-069','KEYWORD-ARGUMENT-GROUP','SYNTAX-COMMAND-SEQUENCE','SECTION-4-5-9-055'],
    'group-empty': ['EXAMPLE-068','EXAMPLE-069','KEYWORD-ARGUMENT-GROUP','SYNTAX-COMMAND-SEQUENCE','SECTION-4-5-9-055'],
    'confirm': ['EXAMPLE-064','MODIFIER-CONFIRM','SECTION-4-5-5-051'],
}
for radix in ('DEC','HEX','OCT','BIN'):
    GROUP_ROWS['radix-'+radix] = ['CONSTANT-RADIX-'+radix,'MODIFIER-RADIX']
for key in METADATA:
    METADATA[key]['contracts'] = ['CMP-LRM244-'+row for row in GROUP_ROWS.get(key.split(':')[0],())]

add("unsupported-direct-block","failure","from spell.lib.registry import REGISTRY; before=mark(); rejects(DriverException,lambda:REGISTRY['TC']._sendBlock([BuildTC('CMD1',config=CFG)],CFG)); effects(before,[])")
