"""Independent p93 schedule/activity controls; no rows promoted before review."""
CASES, METADATA = {}, {}


def group(name,**dimensions):
    assert set(dimensions)=={'positive','boundary','failure','recovery'}
    for dimension,source in dimensions.items():
        key=name+':'+dimension
        CASES[key]=source
        METADATA[key]=dict(contracts=[],dimension=dimension,
            oracle='LRM p93 separates schedule from on-demand activity; original native helpers, exact real RPC receipts, persistent SQL state and reopening, explicit receipt-loss fault injection.')


group('enable',positive="""
assert EnableRanging(config=CFG) is True
assert StartRanging(BBE,ANT,config=CFG) is True
before=mark()
assert EnableRanging(config=CFG) is True
state_effects(before,[('EnableRanging',True,'','')],'RANGING',True)
""",boundary="""
assert EnableRanging(config=CFG) is True
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
before=mark()
assert EnableRanging(CFG) is True
assert EnableRanging(**CFG) is True
state_effects(before,[('EnableRanging',True,'','')]*2,'CALIBRATING',True)
""",failure="""
assert EnableRanging(config=CFG) is True
assert StartRanging(BBE,ANT,config=CFG) is True
before=mark()
rejects(SyntaxException,lambda:EnableRanging(BBE,config=CFG))
assert_no_call(before)
rejects(DriverException,lambda:EnableRanging(config=dict(CFG,IsLocal=True)))
state_effects(before,[],'RANGING',True)
""",recovery="""
assert EnableRanging(config=CFG) is True
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
assert DisableRanging(config=CFG) is True
before=mark()
rejects(DriverException,lambda:EnableRanging(config=dict(CFG,IsLocal=True)))
assert EnableRanging(config=CFG) is True
state_effects(before,[('EnableRanging',True,'','')],'CALIBRATING',True)
""")

group('disable',positive="""
assert EnableRanging(config=CFG) is True
assert StartRanging(BBE,ANT,config=CFG) is True
before=mark()
assert DisableRanging(config=CFG) is True
state_effects(before,[('DisableRanging',True,'','')],'RANGING',False)
""",boundary="""
assert EnableRanging(config=CFG) is True
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
before=mark()
assert DisableRanging(CFG) is True
assert DisableRanging(**CFG) is True
state_effects(before,[('DisableRanging',True,'','')]*2,'CALIBRATING',False)
""",failure="""
assert EnableRanging(config=CFG) is True
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
before=mark()
rejects(SyntaxException,lambda:DisableRanging(ANT,config=CFG))
assert_no_call(before)
rejects(DriverException,lambda:DisableRanging(config=dict(CFG,IsLocal=True)))
state_effects(before,[],'CALIBRATING',True)
""",recovery="""
assert EnableRanging(config=CFG) is True
assert StartRanging(BBE,ANT,config=CFG) is True
before=mark()
rejects(DriverException,lambda:DisableRanging(config=dict(CFG,IsLocal=True)))
assert DisableRanging(config=CFG) is True
state_effects(before,[('DisableRanging',True,'','')],'RANGING',False)
""")

group('on-demand',positive="""
assert DisableRanging(config=CFG) is True
before=mark()
assert StartRanging(BBE,ANT,config=CFG) is True
state_effects(before,[('StartRanging',True,BBE,ANT)],'RANGING',False)
""",boundary="""
assert DisableRanging(config=CFG) is True
before=mark()
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
state_effects(before,[('StartCalibration',True,BBE,ANT)],'CALIBRATING',False)
reopened=fixture('reopen')
assert reopened['migration_error'] is None
equal(reopened['ground']['ranging'],'CALIBRATING')
assert reopened['ground']['ranging_schedule_enabled'] is False
equal(GetAntennaNames(config=CFG),[ANT])
""",failure="""
assert EnableRanging(config=CFG) is True
assert AbortRanging(config=CFG) is True
assert DisableRanging(config=CFG) is True
before=mark()
rejects(DriverException,lambda:StartRanging('MISSING',ANT,config=CFG))
rejects(DriverException,lambda:StartRangingCalibration(BBE,'MISSING',config=CFG))
state_effects(before,[],'READY',False)
""",recovery="""
assert DisableRanging(config=CFG) is True
before=mark()
rejects(DriverException,lambda:StartRanging(BBE,'MISSING',config=CFG))
assert StartRanging(BBE,ANT,config=CFG) is True
state_effects(before,[('StartRanging',True,BBE,ANT)],'RANGING',False)
reopened=fixture('reopen')
assert reopened['migration_error'] is None
equal(reopened['ground']['ranging'],'RANGING')
assert reopened['ground']['ranging_schedule_enabled'] is False
""")

group('abort',positive="""
assert EnableRanging(config=CFG) is True
assert StartRanging(BBE,ANT,config=CFG) is True
assert DisableRanging(config=CFG) is True
before=mark()
assert AbortRanging(config=CFG) is True
state_effects(before,[('AbortRanging',True,'','')],'READY',False)
""",boundary="""
assert DisableRanging(config=CFG) is True
before=mark()
assert AbortRanging(config=CFG) is True
assert AbortRanging(config=CFG) is True
state_effects(before,[('AbortRanging',True,'','')]*2,'READY',False)
""",failure="""
assert EnableRanging(config=CFG) is True
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
before=mark()
rejects(SyntaxException,lambda:AbortRanging(BBE,config=CFG))
assert_no_call(before)
rejects(DriverException,lambda:AbortRanging(config=dict(CFG,IsLocal=True)))
state_effects(before,[],'CALIBRATING',True)
""",recovery="""
assert EnableRanging(config=CFG) is True
assert StartRangingCalibration(BBE,ANT,config=CFG) is True
before=mark()
rejects(DriverException,lambda:AbortRanging(config=dict(CFG,IsLocal=True)))
assert AbortRanging(config=CFG) is True
state_effects(before,[('AbortRanging',True,'','')],'READY',True)
""")

group('migration',positive="""
for legacy in ('RANGING','CALIBRATING'):
    check_legacy_reopen(legacy,legacy,True)
""",boundary="""
check_legacy_reopen('DISABLED','READY',False)
check_legacy_reopen('READY','READY',True)
for active in ('RANGING','CALIBRATING'):
    state=mark()['ground']
    state.update(ranging=active,ranging_schedule_enabled=False)
    encoded=json.dumps(state,indent=1)
    first=fixture('legacy_reopen',encoded=encoded)
    assert first['migration_error'] is None
    equal(first['ground_encoded'],encoded)
    second=fixture('reopen')
    equal(second['ground_encoded'],encoded)
    equal(second['ground'],state)
    equal(GetBasebandNames(config=CFG),[BBE])
""",failure="""
valid=mark()['ground']
for invalid in ({'ranging':'UNKNOWN'},{'ranging':[]},{'ranging':'RANGING','ranging_schedule_enabled':0}):
    encoded=json.dumps(invalid)
    failed=fixture('legacy_reopen',encoded=encoded)
    try:
        assert failed['migration_error'] and failed['migration_error'].startswith('ValueError:')
        equal(failed['ground_encoded'],encoded)
        equal(failed['other_namespaces']['rng-unused'],' { "retain" : [0, false, 42] } ')
    finally:
        restored=fixture('legacy_reopen',encoded=json.dumps(valid))
        assert restored['migration_error'] is None
""",recovery="""
check_legacy_reopen('DISABLED','READY',False)
before=mark()
assert StartRanging(BBE,ANT,config=CFG) is True
state_effects(before,[('StartRanging',True,BBE,ANT)],'RANGING',False)
reopened=fixture('reopen')
assert reopened['migration_error'] is None
equal(reopened['ground']['ranging'],'RANGING')
assert reopened['ground']['ranging_schedule_enabled'] is False
""")

# Last: its intentionally pending receipt must remain unresolved and fenced.
CASES['uncertain-receipt:failure']="""
assert EnableRanging(config=CFG) is True
assert AbortRanging(config=CFG) is True
assert DisableRanging(config=CFG) is True
before=mark()
fixture('arm_receipt_failure')
rejects(DriverException,lambda:StartRanging(BBE,ANT,config=CFG))
after=mark()
equal(after['ground']['ranging'],'RANGING')
assert after['ground']['ranging_schedule_enabled'] is False
delta=after['effects'][len(before['effects']):]
equal(len(delta),1)
equal(delta[0]['state'],'PENDING')
equal(delta[0]['receipt'],None)
calls=after['rpc'][len(before['rpc']):]
equal(len(calls),1)
assert calls[0]['path'].endswith('/StartRanging') and 'Controlled receipt loss' in calls[0]['error']
reopened=fixture('reopen')
assert reopened['migration_error'] is None
equal(reopened['effects'],after['effects'])
rejects(DriverException,lambda:StartRanging(BBE,ANT,config=CFG))
rejects(DriverException,lambda:AbortRanging(config=CFG))
fenced=mark()
equal(fenced['ground'],after['ground'])
equal(fenced['effects'],after['effects'])
attempts=fenced['rpc'][len(after['rpc']):]
equal(len(attempts),2)
assert all('UncertainEffect' in r['error'] and 'response' not in r for r in attempts)
equal(GetBasebandNames(config=CFG),[BBE])
"""
METADATA['uncertain-receipt:failure']=dict(contracts=[],dimension='failure',
    oracle='Actual persisted Ground effect followed by injected receipt loss; persistent unresolved intent fences later actual RPC attempts across reopening, without replay.')
