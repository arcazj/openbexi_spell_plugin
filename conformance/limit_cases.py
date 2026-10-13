"""LRM pp.59–68 contracts through original native SPELL and the real DSS driver."""

CASES, METADATA = {}, {}


def add(name, source, contracts=(), dimension='normal', oracle=None):
    CASES[name] = source
    METADATA[name] = dict(contracts=['CMP-LRM244-' + value for value in contracts],
        dimension=dimension, oracle=oracle or 'Actual native API result, original-schema RPC and persistent ground database agree.')


GROUND = ('FUNCTION-SETGROUNDPARAMETER', 'EXAMPLE-084', 'SECTION-4-7-070')
RESTORE = ('FUNCTION-RESTORENORMALLIMITS', 'EXAMPLE-106', 'SECTION-4-8-9-080')
ALARM = ('FUNCTION-ISALARMED', 'EXAMPLE-107', 'SECTION-4-8-10-081')
THRESHOLDS = ('MODIFIER-LORED', 'MODIFIER-LOYEL', 'MODIFIER-HIYEL', 'MODIFIER-HIRED')
DEFINITION = ('MODIFIER-DEFINITION', 'CONSTANT-LIMIT-TYPE-HARDSOFT') + THRESHOLDS

add('inject.engineering', """
assert SetGroundParameter('TMparam', 12.345, HandleError=False)
equal(GetTM('TMparam', Wait=False, HandleError=False), 12.345)
equal(GetTM('TMparam', ValueFormat=RAW, Wait=False, HandleError=False), 12345)
row = ground()['injections']['TMparam']
equal(row['raw'], 12345)
equal(row['eng'], 12.345)
assert row['valid']
""", GROUND)
add('inject.raw-negative', """
assert SetGroundParameter('TMparam', -12345, ValueFormat=RAW, HandleError=False)
equal(GetTM('TMparam', Wait=False, HandleError=False), -12.345)
equal(ground()['injections']['TMparam']['raw'], -12345)
""", GROUND, 'boundary')
add('inject.list', """
assert SetGroundParameter([['TMparam', 2.5], ['TMparam1', 28.0]], HandleError=False)
equal(GetTM('TMparam', Wait=False, HandleError=False), 2.5)
equal(GetTM('TMparam1', Wait=False, HandleError=False), 28.0)
equal(ground()['injections']['TMparam1']['raw'], 28000)
""", GROUND)
for suffix, call, error in (
    ('no-arguments', 'SetGroundParameter(HandleError=False)', 'SyntaxException'),
    ('extra-arguments', "SetGroundParameter('TMparam',1,2,HandleError=False)", 'SyntaxException'),
    ('missing-value', "SetGroundParameter('TMparam',HandleError=False)", 'SyntaxException'),
    ('malformed-list', "SetGroundParameter([['TMparam',1],['TMparam']],HandleError=False)", 'SyntaxException'),
    ('unknown-name', "SetGroundParameter('NOT.A.PARAMETER',1,HandleError=False)", 'DriverException'),
    ('nonrepresentable', "SetGroundParameter('TMparam',0.0001,HandleError=False)", 'DriverException'),
    ('invalid-format', "SetGroundParameter('TMparam',1,ValueFormat='invalid',HandleError=False)", 'DriverException'),
):
    add('inject.reject.' + suffix, f"unchanged(lambda: {call}, {error})", GROUND, 'failure')

add('get.missing-definition', """
assert RestoreNormalLimits(HandleError=False)
unchanged(lambda: GetLimits('TMparam', HandleError=False), DriverException)
""", (), 'failure')
add('set.definition', """
assert RestoreNormalLimits(HandleError=False)
definition = {LoRed:10.0, LoYel:20.0, HiYel:30.0, HiRed:40.0}
original = dict(definition)
assert SetLimits('TMparam', Definition=definition, HandleError=False)
equal(definition, original)
equal(ground()['limits']['TMparam'], original)
equal(GetLimits('TMparam', Select='GENERIC', HandleError=False), dict(original, Type=HARDSOFT, Active=True))
""", DEFINITION + ('EXAMPLE-096',))
for suffix, args in (('default', ''), ('all', ', Select=ALL'), ('active', ', Select=ACTIVE')):
    add('get.' + suffix, f"""
seed()
equal(GetLimits('TMparam'{args}, HandleError=False), {{'GENERIC': expected_definition()}})
""", ('CONSTANT-LIMIT-SELECTION-ACTIVE', 'EXAMPLE-088') if suffix == 'active' else ())
add('get.identifier', "seed()\nequal(GetLimits('TMparam', Select='GENERIC', HandleError=False), expected_definition())",
    ('EXAMPLE-089',))
for key in ('LoRed', 'LoYel', 'HiYel', 'HiRed', 'Type', 'Active'):
    add('get.property.' + key, "seed()\nequal(GetLimits('TMparam', Select='GENERIC', Value=" + key +
        ", HandleError=False), expected_definition()[" + key + "])", ('EXAMPLE-092',) if key == 'LoRed' else ())
add('set.dictionary', """
assert RestoreNormalLimits(HandleError=False)
values = {'GENERIC': {LoRed:10, LoYel:20, HiYel:30, HiRed:40}}
assert SetLimits('TMparam', Limits=values, HandleError=False)
equal(ground()['limits']['TMparam'], values['GENERIC'])
equal(GetLimits('TMparam', HandleError=False), {'GENERIC': expected_definition()})
""", (), oracle='One real driver-defined record is accepted through Limits; multi-definition LRM example remains open.')
add('set.partial-threshold', """
seed()
assert SetLimits('TMparam', LoYel=19, HandleError=False)
expected = expected_definition(); expected[LoYel] = 19
equal(GetLimits('TMparam', Select='GENERIC', HandleError=False), expected)
equal(ground()['limits']['TMparam'], {LoRed:10,LoYel:19,HiYel:30,HiRed:40})
""", THRESHOLDS)
add('set.midpoint-parameters', """
assert RestoreNormalLimits(HandleError=False)
assert SetLimits('TMparam', Midpoint=25.0, Tolerance=5.0, HandleError=False)
equal(ground()['limits']['TMparam'], {LoRed:20,LoYel:20,HiYel:30,HiRed:30})
""", ('MODIFIER-MIDPOINT',), 'boundary')
add('set.midpoint-definition-unchanged', """
definition = {Midpoint:0.0, Tolerance:0.0}
assert SetLimits('TMparam', Definition=definition, HandleError=False)
equal(definition, {Midpoint:0.0, Tolerance:0.0})
equal(ground()['limits']['TMparam'], {LoRed:0,LoYel:0,HiYel:0,HiRed:0})
""", ('MODIFIER-MIDPOINT', 'MODIFIER-DEFINITION'), 'boundary')
add('set.midpoint-dictionary-unchanged', """
values = {'GENERIC': {Midpoint:25, Tolerance:5}}
assert SetLimits('TMparam', Limits=values, HandleError=False)
equal(values, {'GENERIC': {Midpoint:25,Tolerance:5}})
equal(ground()['limits']['TMparam'], {LoRed:20,LoYel:20,HiYel:30,HiRed:30})
""", (), 'boundary')

for suffix, call, error in (
    ('get-extra-argument', "GetLimits('TMparam','extra',HandleError=False)", 'SyntaxException'),
    ('alarm-extra-argument', "IsAlarmed('TMparam','extra',HandleError=False)", 'SyntaxException'),
    ('restore-extra-argument', "RestoreNormalLimits('extra',HandleError=False)", 'SyntaxException'),
    ('restore-unknown-modifier', "RestoreNormalLimits(Unknown=True,HandleError=False)", 'DriverException'),
    ('get-unknown-id', "GetLimits('TMparam',Select='ABSENT',HandleError=False)", 'DriverException'),
    ('get-invalid-selector', "GetLimits('TMparam',Select=[],HandleError=False)", 'DriverException'),
    ('get-property-needs-id', "GetLimits('TMparam',Select=ALL,Value=LoRed,HandleError=False)", 'DriverException'),
    ('get-unavailable-property', "GetLimits('TMparam',Select='GENERIC',Value=Hysteresis,HandleError=False)", 'DriverException'),
    ('set-extra-argument', "SetLimits('TMparam',{},HandleError=False)", 'SyntaxException'),
    ('set-unknown-id', "SetLimits('TMparam',Select='ABSENT',LoRed=9,HandleError=False)", 'DriverException'),
    ('set-boolean', "SetLimits('TMparam',LoRed=True,HandleError=False)", 'DriverException'),
    ('set-unordered', "SetLimits('TMparam',LoRed=21,HandleError=False)", 'DriverException'),
    ('set-nan', "SetLimits('TMparam',LoRed=float('nan'),HandleError=False)", 'DriverException'),
    ('set-infinity', "SetLimits('TMparam',HiRed=float('inf'),HandleError=False)", 'DriverException'),
    ('set-raw-unsupported', "SetLimits('TMparam',LoRed=9,ValueFormat=RAW,HandleError=False)", 'DriverException'),
    ('set-status-unsupported', "SetLimits('TMparam',Definition={Nominal:['NORMAL']},HandleError=False)", 'DriverException'),
    ('set-spike-unsupported', "SetLimits('TMparam',Type=SPIKE,Definition={Delta:2},HandleError=False)", 'DriverException'),
    ('set-inactive-unsupported', "SetLimits('TMparam',Definition={LoRed:9,Active:False},HandleError=False)", 'DriverException'),
    ('set-multiple-unsupported', "SetLimits('TMparam',Limits={'GENERIC':{LoRed:9},'OTHER':{LoRed:1}},HandleError=False)", 'DriverException'),
):
    add('reject.' + suffix, f"seed()\nunchanged(lambda: {call}, {error})", (), 'failure',
        oracle='Rejected request leaves both persistent ground state and effect journal unchanged; unsupported feature remains open.')
add('set.partial-needs-initial-definition', """
assert RestoreNormalLimits(HandleError=False)
unchanged(lambda: SetLimits('TMparam', LoRed=10, HandleError=False), DriverException)
""", (), 'failure')

for value, alarm in ((9.999, True), (10.0, True), (19.999, True), (20.0, False), (25.0, False), (30.0, False), (30.001, True), (40.0, True), (40.001, True)):
    add('alarm.' + str(value), f"""
seed()
assert SetGroundParameter('TMparam', {value!r}, HandleError=False)
equal(GetTM('TMparam', Wait=False, HandleError=False), {value!r})
equal(IsAlarmed('TMparam', HandleError=False), {alarm!r})
equal(ground()['limits']['TMparam'], {{LoRed:10,LoYel:20,HiYel:30,HiRed:40}})
""", ALARM, 'boundary')
add('restore.all-parameters', """
seed()
assert SetLimits('TMparam1', Definition={LoRed:10,LoYel:20,HiYel:30,HiRed:40}, HandleError=False)
assert SetGroundParameter('TMparam', 50, HandleError=False)
assert IsAlarmed('TMparam', HandleError=False)
injections = ground()['injections']
assert RestoreNormalLimits(HandleError=False)
equal(ground()['limits'], {})
equal(ground()['injections'], injections)
assert not IsAlarmed('TMparam', HandleError=False)
rejects(DriverException, lambda: GetLimits('TMparam', HandleError=False))
rejects(DriverException, lambda: GetLimits('TMparam1', HandleError=False))
assert RestoreNormalLimits(HandleError=False)
""", RESTORE + ALARM)
add('get.failure-prompt-cancel', """
assert RestoreNormalLimits(HandleError=False)
plan_prompt(['SKIP','REPEAT','CANCEL','ABORT'], 'CANCEL')
equal(GetLimits('TMparam', PromptFailure=True), None)
equal(ground()['limits'], {})
""", (), 'failure')
add('set.failure-prompt-cancel', """
seed()
before = ground()
plan_prompt(['SKIP','REPEAT','CANCEL','ABORT'], 'CANCEL')
equal(SetLimits('TMparam', LoRed=100, PromptFailure=True), False)
equal(ground(), before)
""", (), 'failure')

add('inject.reject.nonnumeric', "unchanged(lambda: SetGroundParameter('TMparam','not-a-number',HandleError=False), DriverException)", GROUND, 'failure')
add('set.roundtrip-dictionary', """
seed()
values = GetLimits('TMparam', Select=ACTIVE, HandleError=False)
values['GENERIC'][LoRed] = 9
assert SetLimits('TMparam', Limits=values, HandleError=False)
equal(GetLimits('TMparam', Select=ACTIVE, HandleError=False), values)
equal(ground()['limits']['TMparam'][LoRed], 9)
""", ('EXAMPLE-094',))
add('set.roundtrip-definition', """
seed()
values = GetLimits('TMparam', Select=ACTIVE, HandleError=False)['GENERIC']
values[LoRed] = 8
assert SetLimits('TMparam', Definition=values, Select='GENERIC', HandleError=False)
equal(GetLimits('TMparam', Select='GENERIC', HandleError=False), values)
equal(ground()['limits']['TMparam'][LoRed], 8)
""", ('EXAMPLE-095',))
add('set.midpoint-selected', """
seed()
assert SetLimits('TMparam', Select='GENERIC', Midpoint=10.0, Tolerance=0.5, HandleError=False)
equal(ground()['limits']['TMparam'], {LoRed:9.5,LoYel:9.5,HiYel:10.5,HiRed:10.5})
""", ('EXAMPLE-099','MODIFIER-MIDPOINT'))
add('set.reject.negative-tolerance', "seed()\nunchanged(lambda: SetLimits('TMparam',Midpoint=25,Tolerance=-1,HandleError=False), DriverException)", ('MODIFIER-MIDPOINT',), 'failure')
add('set.reject.three-input-families', """
seed()
unchanged(lambda: SetLimits('TMparam', Definition={LoRed:1}, Limits={'GENERIC':{LoRed:2}}, LoRed=3, HandleError=False), SyntaxException)
""", (), 'failure')
add('inject.recovery', """
unchanged(lambda: SetGroundParameter('TMparam',0.0001,HandleError=False), DriverException)
assert SetGroundParameter('TMparam', -1.234, HandleError=False)
equal(GetTM('TMparam', Wait=False, HandleError=False), -1.234)
equal(ground()['injections']['TMparam']['raw'], -1234)
""", GROUND, 'recovery')
add('limit.recovery', """
seed()
unchanged(lambda: SetLimits('TMparam', LoRed=100, HandleError=False), DriverException)
assert SetLimits('TMparam', LoRed=9, HandleError=False)
row = expected_definition(); row[LoRed] = 9
equal(GetLimits('TMparam', Select='GENERIC', HandleError=False), row)
assert SetLimits('TMparam', Select='GENERIC', Midpoint=25, Tolerance=5, HandleError=False)
equal(ground()['limits']['TMparam'], {LoRed:20,LoYel:20,HiYel:30,HiRed:30})
assert SetGroundParameter('TMparam', 35, HandleError=False)
assert IsAlarmed('TMparam', HandleError=False)
assert RestoreNormalLimits(HandleError=False)
assert not IsAlarmed('TMparam', HandleError=False)
rejects(DriverException, lambda: GetLimits('TMparam', HandleError=False))
seed()
equal(GetLimits('TMparam', HandleError=False), {'GENERIC':expected_definition()})
""", RESTORE + ALARM + DEFINITION + ('MODIFIER-MIDPOINT',), 'recovery')

add('inject.failure-prompt-cancel', """
before = ground()
plan_prompt(['SKIP','REPEAT','CANCEL','ABORT'], 'CANCEL')
equal(SetGroundParameter('TMparam', 'not-a-number', OnFailure=SKIP|REPEAT|CANCEL|ABORT, PromptFailure=True), False)
equal(ground(), before)
""", GROUND, 'failure')
add('alarm.live-dss-sample', """
assert RestoreNormalLimits(HandleError=False)
assert 'TM.POWER.BUS_VOLTAGE' not in ground()['injections']
assert SetLimits('TM.POWER.BUS_VOLTAGE', Definition={LoRed:20,LoYel:25,HiYel:30,HiRed:35}, HandleError=False)
equal(GetTM('TM.POWER.BUS_VOLTAGE', Wait=False, HandleError=False), 28.0)
assert not IsAlarmed('TM.POWER.BUS_VOLTAGE', HandleError=False)
assert SetLimits('TM.POWER.BUS_VOLTAGE', HiYel=27.0, HandleError=False)
assert IsAlarmed('TM.POWER.BUS_VOLTAGE', HandleError=False)
assert RestoreNormalLimits(HandleError=False)
assert not IsAlarmed('TM.POWER.BUS_VOLTAGE', HandleError=False)
""", ALARM + RESTORE)

for value in (-2**63, 2**63-1):
    add('inject.boundary.int64.' + str(value), f"""
assert SetGroundParameter('TMparam', {value}, ValueFormat=RAW, HandleError=False)
equal(GetTM('TMparam', ValueFormat=RAW, Wait=False, HandleError=False), {value})
equal(ground()['injections']['TMparam']['raw'], {value})
""", GROUND, 'boundary')
for value in (-2**63-1, 2**63, 2**80):
    add('inject.reject.int64.' + str(value), f"unchanged(lambda: SetGroundParameter('TMparam',{value},ValueFormat=RAW,HandleError=False), DriverException)", GROUND, 'failure')
    add('set.reject.int64.' + str(value), f"unchanged(lambda: SetLimits('TMparam',Definition={{LoRed:{min(value,0)},LoYel:0,HiYel:1,HiRed:{max(value,1)}}},HandleError=False), DriverException)", (), 'failure')
add('set.boundary.int64', """
values = {LoRed:-2**63,LoYel:0,HiYel:1,HiRed:2**63-1}
assert SetLimits('TMparam', Definition=values, HandleError=False)
equal(ground()['limits']['TMparam'], values)
equal(GetLimits('TMparam', Select='GENERIC', Value=LoRed, HandleError=False), -2**63)
equal(GetLimits('TMparam', Select='GENERIC', Value=HiRed, HandleError=False), 2**63-1)
""", DEFINITION, 'boundary')
add('inject.boundary.recovery', """
unchanged(lambda: SetGroundParameter('TMparam',2**80,ValueFormat=RAW,HandleError=False), DriverException)
assert SetGroundParameter('TMparam', 1.234, HandleError=False)
equal(GetTM('TMparam', Wait=False, HandleError=False), 1.234)
""", GROUND, 'recovery')
