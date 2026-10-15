"""LRM pp93–95: bounded actual ranging effects and catalog results."""
CASES, METADATA = {}, {}


def group(name, contracts, **dimensions):
    assert set(dimensions) == {'positive', 'boundary', 'failure', 'recovery'}
    for dimension, source in dimensions.items():
        key=name+':'+dimension
        CASES[key]=source
        METADATA[key]=dict(contracts=['CMP-LRM244-'+value for value in contracts],
            dimension=dimension,
            oracle='LRM pp93–95; original native helper and adapter, real binary RPC, independently decoded persistent SQL state/receipts and actual native prompt choices.')


group('enable', ['FUNCTION-ENABLERANGING','EXAMPLE-169'], positive="""
assert DisableRanging(config=CFG) is True
before=mark()
assert EnableRanging(config=CFG) is True
assert_effects(before,[('EnableRanging',True,'','')],'READY')
""", boundary="""
assert EnableRanging(config=CFG) is True
before=mark()
assert EnableRanging(CFG) is True
assert EnableRanging(**CFG) is True
assert_effects(before,[('EnableRanging',True,'','')]*2,'READY')
""", failure="""
before=mark()
rejects(SyntaxException,lambda:EnableRanging(BBE,config=CFG))
rejects(SyntaxException,lambda:EnableRanging(BBE,ANT,config=CFG))
assert_no_call(before)
rejects(DriverException,lambda:EnableRanging(config=dict(CFG,IsLocal=True)))
assert_effects(before,[],before['ground']['ranging'])
""", recovery="""
before=mark()
rejects(DriverException,lambda:EnableRanging(config=dict(CFG,IsLocal=True)))
assert EnableRanging(config=CFG) is True
assert_effects(before,[('EnableRanging',True,'','')],'READY')
""")

group('disable', ['FUNCTION-DISABLERANGING','EXAMPLE-169'], positive="""
assert EnableRanging(config=CFG) is True
before=mark()
assert DisableRanging(config=CFG) is True
assert_effects(before,[('DisableRanging',True,'','')],'DISABLED')
""", boundary="""
assert DisableRanging(config=CFG) is True
before=mark()
assert DisableRanging(CFG) is True
assert DisableRanging(**CFG) is True
assert_effects(before,[('DisableRanging',True,'','')]*2,'DISABLED')
""", failure="""
before=mark()
rejects(SyntaxException,lambda:DisableRanging(BBE,config=CFG))
rejects(SyntaxException,lambda:DisableRanging(BBE,ANT,config=CFG))
assert_no_call(before)
rejects(DriverException,lambda:DisableRanging(config=dict(CFG,IsLocal=True)))
assert_effects(before,[],before['ground']['ranging'])
""", recovery="""
before=mark()
rejects(DriverException,lambda:DisableRanging(config=dict(CFG,IsLocal=True)))
assert DisableRanging(config=CFG) is True
assert_effects(before,[('DisableRanging',True,'','')],'DISABLED')
""")

group('start-single', ['EXAMPLE-170'], positive="""
assert EnableRanging(config=CFG) is True
before=mark()
assert StartRanging(BBE,ANT,config=CFG) is True
assert_effects(before,[('StartRanging',True,BBE,ANT)],'RANGING')
""", boundary="""
assert DisableRanging(config=CFG) is True
before=mark()
assert StartRanging(BBE,ANT,config=CFG) is False
assert_effects(before,[('StartRanging',False,BBE,ANT)],'DISABLED')
assert EnableRanging(config=CFG) is True
before=mark()
assert StartRanging(BBE,ANT,config=CFG) is True
assert StartRanging(BBE,ANT,config=CFG) is True
assert_effects(before,[('StartRanging',True,BBE,ANT)]*2,'RANGING')
""", failure="""
before=mark()
for args in ((),(BBE,),(BBE,ANT,'extra'),(1,ANT),(BBE,1)):
    rejects(SyntaxException,lambda:StartRanging(*args,config=CFG))
assert_no_call(before)
for pair in (('MISSING',ANT),(BBE,'MISSING'),('',ANT),(BBE,'')):
    rejects(DriverException,lambda:StartRanging(*pair,config=CFG))
assert_effects(before,[],before['ground']['ranging'])
""", recovery="""
assert EnableRanging(config=CFG) is True
before=mark()
rejects(DriverException,lambda:StartRanging('MISSING',ANT,config=CFG))
assert StartRanging(BBE,ANT,config=CFG) is True
assert_effects(before,[('StartRanging',True,BBE,ANT)],'RANGING')
""")

group('calibration-single', ['EXAMPLE-175'], positive="""
assert EnableRanging(config=CFG) is True
before=mark()
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
assert_effects(before,[('StartCalibration',True,BBE,ANT)],'CALIBRATING')
""", boundary="""
assert DisableRanging(config=CFG) is True
before=mark()
assert StartRangingCalibration(BBE,ANT,config=CFG) is False
assert_effects(before,[('StartCalibration',False,BBE,ANT)],'DISABLED')
assert EnableRanging(config=CFG) is True
before=mark()
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
assert_effects(before,[('StartCalibration',True,BBE,ANT)]*2,'CALIBRATING')
""", failure="""
before=mark()
for args in ((),(BBE,),(BBE,ANT,'extra'),(1,ANT),(BBE,1)):
    rejects(SyntaxException,lambda:StartRangingCalibration(*args,config=CFG))
assert_no_call(before)
for pair in (('MISSING',ANT),(BBE,'MISSING'),('',ANT),(BBE,'')):
    rejects(DriverException,lambda:StartRangingCalibration(*pair,config=CFG))
assert_effects(before,[],before['ground']['ranging'])
""", recovery="""
assert EnableRanging(config=CFG) is True
before=mark()
rejects(DriverException,lambda:StartRangingCalibration('MISSING',ANT,config=CFG))
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
assert_effects(before,[('StartCalibration',True,BBE,ANT)],'CALIBRATING')
""")

group('abort-single', ['EXAMPLE-172'], positive="""
assert EnableRanging(config=CFG) is True
assert StartRanging(BBE,ANT,config=CFG) is True
before=mark()
assert AbortRanging(config=CFG) is True
assert_effects(before,[('AbortRanging',True,'','')],'READY')
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
before=mark()
assert AbortRanging(config=CFG) is True
assert_effects(before,[('AbortRanging',True,'','')],'READY')
""", boundary="""
assert DisableRanging(config=CFG) is True
before=mark()
assert AbortRanging(config=CFG) is False
assert_effects(before,[('AbortRanging',False,'','')],'DISABLED')
assert EnableRanging(config=CFG) is True
before=mark()
assert AbortRanging(config=CFG) is True
assert AbortRanging(config=CFG) is True
assert_effects(before,[('AbortRanging',True,'','')]*2,'READY')
""", failure="""
before=mark()
rejects(SyntaxException,lambda:AbortRanging(BBE,config=CFG))
rejects(SyntaxException,lambda:AbortRanging(BBE,ANT,config=CFG))
assert_no_call(before)
rejects(DriverException,lambda:AbortRanging(config=dict(CFG,IsLocal=True)))
assert_effects(before,[],before['ground']['ranging'])
""", recovery="""
assert EnableRanging(config=CFG) is True
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
before=mark()
rejects(DriverException,lambda:AbortRanging(config=dict(CFG,IsLocal=True)))
assert AbortRanging(config=CFG) is True
assert_effects(before,[('AbortRanging',True,'','')],'READY')
""")

for label,function,method,expected,contract in (
    ('baseband-names','GetBasebandNames','GetBasebandNames','BBE','FUNCTION-GETBASEBANDNAMES'),
    ('antenna-names','GetAntennaNames','GetAntennaNames','ANT','FUNCTION-GETANTENNANAMES')):
    group(label,[contract,'EXAMPLE-174'],positive=f"""
before=mark()
actual={function}(config=CFG)
assert type(actual) is list
equal(actual,[{expected}])
assert_read(before,'{method}',[{expected}])
""",boundary=f"""
first={function}(config=CFG)
first.append('LOCAL-ONLY')
before=mark()
equal({function}(config=CFG),[{expected}])
assert_read(before,'{method}',[{expected}])
""",failure=f"""
before=mark()
rejects(SyntaxException,lambda:{function}('extra',config=CFG))
assert_no_call(before)
rejects(DriverException,lambda:{function}(config=dict(CFG,IsLocal=True)))
assert_effects(before,[],before['ground']['ranging'])
""",recovery=f"""
rejects(DriverException,lambda:{function}(config=dict(CFG,IsLocal=True)))
before=mark()
equal({function}(config=CFG),[{expected}])
assert_read(before,'{method}',[{expected}])
""")

group('policy', [], positive="""
before=mark()
plan_prompt(['SKIP','REPEAT','CANCEL','ABORT'],'CANCEL')
assert StartRanging('MISSING',ANT,OnFailure=SKIP|REPEAT|CANCEL|ABORT,PromptFailure=True) is False
assert_effects(before,[],before['ground']['ranging'])
""",boundary="""
before=mark()
plan_prompt(['SKIP','REPEAT','CANCEL','ABORT'],'REPEAT')
plan_prompt(['SKIP','REPEAT','CANCEL','ABORT'],'CANCEL')
assert StartRanging('MISSING',ANT,OnFailure=SKIP|REPEAT|CANCEL|ABORT,PromptFailure=True) is False
after=assert_effects(before,[],before['ground']['ranging'])
rows=after['rpc'][len(before['rpc']):]
equal(len(rows),2)
assert all(r['path'].endswith('/StartRanging') and 'error' in r for r in rows)
""",failure="""
before=mark()
plan_prompt(['SKIP','REPEAT','CANCEL','ABORT'],'CANCEL')
assert StartRangingCalibration('MISSING',ANT,OnFailure=SKIP|REPEAT|CANCEL|ABORT,PromptFailure=True) is False
assert_effects(before,[],before['ground']['ranging'])
""",recovery="""
assert EnableRanging(config=CFG) is True
before=mark()
rejects(DriverException,lambda:StartRanging('MISSING',ANT,config=CFG))
assert StartRanging(BBE,ANT,config=CFG) is True
assert AbortRanging(config=CFG) is True
assert_effects(before,[('StartRanging',True,BBE,ANT),('AbortRanging',True,'','')],'READY')
""")

group('interrupt-policy', [], positive="""
before=mark()
assert EnableRanging(config=dict(CFG,AllowInterrupt=True)) is True
assert_effects(before,[('EnableRanging',True,'','')],'READY')
""",boundary="""
for value in (False,True):
    before=mark()
    assert DisableRanging(config=dict(CFG,AllowInterrupt=value)) is True
    assert_effects(before,[('DisableRanging',True,'','')],'DISABLED')
    before=mark()
    equal(GetBasebandNames(config=dict(CFG,AllowInterrupt=value)),[BBE])
    assert_read(before,'GetBasebandNames',[BBE])
""",failure="""
before=mark()
for value in (0,1,'False',None,[],{}):
    rejects(DriverException,lambda:EnableRanging(config=dict(CFG,AllowInterrupt=value)))
assert_no_call(before)
""",recovery="""
before=mark()
rejects(DriverException,lambda:EnableRanging(config=dict(CFG,AllowInterrupt='False')))
assert EnableRanging(config=dict(CFG,AllowInterrupt=False)) is True
assert_effects(before,[('EnableRanging',True,'','')],'READY')
""")
