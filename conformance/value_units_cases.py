"""LRM48,112-113 TC argument casting and units, independent of driver support."""
CASES={}
METADATA={}


def add(group,dimension,source,rows=('MODIFIER-VALUETYPE',)):
    key=group+':'+dimension
    CASES[key]=source
    METADATA[key]=dict(dimension=dimension,contracts=['CMP-LRM244-'+row for row in rows],
        oracle='Original native BuildTC object inspected against literal Python values/types and documented metadata; real DSS commands have five immutable stage receipts and one delivery per stage; rejected sends have no effect.')


add('long','positive',"before=mark(); item,value=argument('42',{ValueType:LONG}); exact(value,42,LONG); no_send(before)")
add('long','boundary',"before=mark(); exact(argument(-3.9,{ValueType:LONG})[1],-3,LONG); exact(argument(2**200,{ValueType:LONG})[1],2**200,LONG); exact(argument(True,{ValueType:LONG})[1],1,LONG); no_send(before)")
add('long','failure',"before=mark(); rejects(SyntaxException,lambda:argument('bad',{ValueType:LONG})); rejects(SyntaxException,lambda:argument(float('inf'),{ValueType:LONG})); no_send(before)")
add('long','recovery',"before=mark(); item,value=argument('15',{ValueType:LONG},name='ARG2'); exact(value,15,LONG); sent_argument(before,item,15,'LONG','ARG2')")
add('string','positive',"before=mark(); item,value=argument(42,{ValueType:STRING}); exact(value,'42',STRING); no_send(before)")
add('string','boundary',"before=mark(); exact(argument('',{ValueType:STRING})[1],'',STRING); exact(argument(False,{ValueType:STRING})[1],'False',STRING); exact(argument('ÃŽÂ¼s/Ã‚Â°C',{ValueType:STRING})[1],'ÃŽÂ¼s/Ã‚Â°C',STRING); no_send(before)")
add('string','failure',"before=mark(); item,value=argument(42,{ValueType:STRING}); rejects(DriverException,lambda:Send(command=item,config=CFG)); effects(before,[])")
add('string','recovery',"before=mark(); item,value=argument('NOMINAL',{ValueType:STRING},name='MODE',command='TC.SIMULATOR.SET_MODE'); exact(value,'NOMINAL',STRING); sent_argument(before,item,'NOMINAL','STRING','MODE')")
add('float','positive',"before=mark(); item,value=argument(42,{ValueType:FLOAT}); exact(value,42.0,FLOAT); no_send(before)")
add('float','boundary',"before=mark(); import math; value=argument('-0.0',{ValueType:FLOAT})[1]; exact(value,-0.0,FLOAT); equal(math.copysign(1.0,value.get()),-1.0); exact(argument('1e6',{ValueType:FLOAT})[1],1000000.0,FLOAT); no_send(before)")
add('float','failure',"before=mark(); rejects(SyntaxException,lambda:argument('bad',{ValueType:FLOAT})); rejects(SyntaxException,lambda:argument(2**2000,{ValueType:FLOAT})); no_send(before)")
add('float','recovery',"before=mark(); item,value=argument('1.25',{ValueType:FLOAT}); exact(value,1.25,FLOAT); sent_argument(before,item,1.25,'FLOAT'); equal(mark()['state']['payload']['setpoint_milli'],1250)")
add('boolean','positive',"before=mark(); exact(argument(0,{ValueType:BOOLEAN})[1],False,BOOLEAN); exact(argument(1,{ValueType:BOOLEAN})[1],True,BOOLEAN); no_send(before)")
add('boolean','boundary',"before=mark(); exact(argument('',{ValueType:BOOLEAN})[1],False,BOOLEAN); exact(argument('False',{ValueType:BOOLEAN})[1],True,BOOLEAN); exact(argument([],{ValueType:BOOLEAN})[1],False,BOOLEAN); no_send(before)")
add('boolean','failure',"before=mark(); item,value=argument(True,{ValueType:BOOLEAN}); rejects(DriverException,lambda:Send(command=item,config=CFG)); effects(before,[])")
add('boolean','recovery',"before=mark(); item,value=argument(True,{ValueType:BOOLEAN}); rejects(DriverException,lambda:Send(command=item,config=CFG)); effects(before,[]); fresh=mark(); item,value=argument(1,{ValueType:BOOLEAN},name='FORCE',command='TC.SIMULATOR.RESET'); exact(value,True,BOOLEAN); sent_argument(fresh,item,True,'BOOLEAN','FORCE'); wire_argument(fresh,True,BOOLEAN); fresh=mark(); item,value=argument(1.0); sent_argument(fresh,item,1.0,'FLOAT')")
add('time','positive',"before=mark(); item,value=argument('01-Jan-1970 00:00:00',{ValueType:TIME}); assert type(value.get()) is TIME; assert value.get().isAbs(); equal(value.get().abs(),0.0); equal(value.vtype(),DATETIME); no_send(before)")
add('time','boundary',"before=mark(); item,value=argument(-1.25,{ValueType:TIME}); assert type(value.get()) is TIME; assert value.get().isRel(); equal(value.get().rel(),-1.25); equal(value.vtype(),RELTIME); original=TIME('29-Feb-2024 12:00:00'); copied=argument(original,{ValueType:TIME})[1]; assert copied.get() is not original; equal(copied.get().abs(),1709208000.0); no_send(before)")
add('time','failure',"before=mark(); rejects(SyntaxException,lambda:argument('invalid-time',{ValueType:TIME})); no_send(before)")
add('time','recovery',"before=mark(); item,value=argument(1.25,{ValueType:TIME}); equal(value.get().rel(),1.25); rejects(DriverException,lambda:Send(command=item,config=CFG)); effects(before,[]); fresh=mark(); item,value=argument('2.5',{ValueType:FLOAT}); sent_argument(fresh,item,2.5,'FLOAT')")
add('inference','positive',"before=mark(); exact(argument(1)[1],1,LONG); exact(argument(1.0)[1],1.0,FLOAT); exact(argument('x')[1],'x',STRING); exact(argument(False)[1],False,BOOLEAN); no_send(before)")
add('inference','boundary',"before=mark(); exact(argument(0,{Units:''})[1],0,LONG); t=argument(TIME(0))[1]; assert type(t.get()) is TIME; equal(t.vtype(),RELTIME); no_send(before)")
add('inference','failure',"before=mark(); rejects(SyntaxException,lambda:argument(1,{ValueType:'bogus'})); rejects(SyntaxException,lambda:argument(1,{ValueType:None})); no_send(before)")
add('inference','recovery',"before=mark(); item,value=argument(1.5); sent_argument(before,item,1.5,'FLOAT')")
add('units','positive',"before=mark(); item,value=argument(1.25,{Units:'deg'}); exact(value,1.25,FLOAT); equal(value.units(),'deg'); no_send(before)",('MODIFIER-UNITS',))
add('units','boundary',"before=mark(); equal(argument(1.0,{Units:''})[1].units(),''); equal(argument(1.0,{Units:'ÃŽÂ¼s/Ã‚Â°C'})[1].units(),'ÃŽÂ¼s/Ã‚Â°C'); equal(argument(1.0,{Units:'u'*8193})[1].units(),'u'*8193); no_send(before)",('MODIFIER-UNITS',))
add('units','failure',"before=mark(); rejects(SyntaxException,lambda:argument(1.0,{Units:42})); rejects(SyntaxException,lambda:argument(1.0,{Units:None})); rejects(SyntaxException,lambda:argument(1.0,{Units:False})); no_send(before)",('MODIFIER-UNITS',))
add('units','recovery',"before=mark(); item,value=argument(2.5,{Units:'deg'}); equal(value.units(),'deg'); rejects(DriverException,lambda:Send(command=item,config=CFG)); no_send(before); item['ARG1']=[2.5,{Units:''}]; equal(item._getParams()[0].value.units(),''); sent_argument(before,item,2.5,'FLOAT')",('MODIFIER-UNITS',))

add('time-alias','positive',"before=mark(); item,value=argument('01-Jan-1970 00:00:00',{ValueType:DATETIME}); equal(value.get().abs(),0.0); equal(value.vtype(),DATETIME); no_send(before)")
add('time-alias','boundary',"before=mark(); item,value=argument(0,{ValueType:RELTIME}); equal(value.get().rel(),0.0); equal(value.vtype(),RELTIME); no_send(before)")
add('time-alias','failure',"before=mark(); rejects(SyntaxException,lambda:argument('01-Jan-1970 00:00:00',{ValueType:RELTIME})); rejects(SyntaxException,lambda:argument(0,{ValueType:DATETIME})); no_send(before)")
add('time-alias','recovery',"before=mark(); item,value=argument('+0 00:00:01.125',{ValueType:RELTIME}); equal(value.get().rel(),1.125); equal(value.vtype(),RELTIME); no_send(before)")
add('atomic-edit','positive',"before=mark(); item,value=argument(1.0); item['ARG1']=['2.25',{ValueType:FLOAT,Units:'V'}]; current=item._getParams()[0].value; exact(current,2.25,FLOAT); equal(current.units(),'V'); no_send(before)",('MODIFIER-VALUETYPE','MODIFIER-UNITS'))
add('atomic-edit','boundary',"before=mark(); item,value=argument(0.0,{Units:'V'}); item['ARG1']=[0.0,{Units:''}]; equal(item._getParams()[0].value.units(),''); no_send(before)",('MODIFIER-UNITS',))
add('atomic-edit','failure',"before=mark(); item,value=argument(1.25,{Units:'V'}); rejects(SyntaxException,lambda:item.__setitem__('ARG1',['bad',{ValueType:FLOAT}])); assert item._getParams()[0].value is value; rejects(SyntaxException,lambda:item.__setitem__('ARG1',[2.0,{Units:False}])); assert item._getParams()[0].value is value; exact(value,1.25,FLOAT); equal(value.units(),'V'); no_send(before)",('MODIFIER-VALUETYPE','MODIFIER-UNITS'))
add('atomic-edit','recovery',"before=mark(); item,value=argument(1.0,{Units:'V'}); item['ARG1']=['3.5',{ValueType:FLOAT}]; sent_argument(before,item,3.5,'FLOAT')",('MODIFIER-VALUETYPE','MODIFIER-UNITS'))
add('wire-range','failure',"before=mark(); item,value=argument(2**100,{ValueType:LONG},name='ARG2'); exact(value,2**100,LONG); rejects(DriverException,lambda:Send(command=item,config=CFG)); no_send(before)",())
add('wire-range','recovery',"before=mark(); item,value=argument('65535',{ValueType:LONG},name='ARG2'); sent_argument(before,item,65535,'LONG','ARG2')",())
