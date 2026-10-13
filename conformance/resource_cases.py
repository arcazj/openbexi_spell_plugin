"""LRM pp69/80 resource and GDB mapping oracles for the declared GENERIC GCS."""
CASES, METADATA = {}, {}


def group(name, contracts, **dimensions):
    assert set(dimensions) == {'positive', 'boundary', 'failure', 'recovery'}
    for dimension, source in dimensions.items():
        identifier = name + ':' + dimension
        CASES[identifier] = source
        METADATA[identifier] = dict(contracts=['CMP-LRM244-' + value for value in contracts],
            dimension=dimension, oracle='LRM pp69/80: original native helpers and GDB, actual binary RPC, independent persistent ground-state observation',
            evidence_kind='native-resource-contract')


group('resource-read', ['FUNCTION-GETRESOURCE', 'EXAMPLE-112'], positive="""
equal(GetResource('value', HandleError=False), 21)
equal(fixture('resource_state')['resources']['value'], 21)
""", boundary="""
for value in (0, False, '', [], {}, -(2**63), 2**63-1, 2.5, 'café λ', [False, {'items':[0, 1]}], {'PromptUser':'literal data','Wait':False}):
    assert SetResource('value', value, HandleError=False) is True
    actual = GetResource('value', HandleError=False)
    equal(actual, value)
    assert type(actual) is type(value), (actual, value)
    equal(fixture('resource_state')['resources']['value'], value)
""", failure="""
rejects(DriverException, lambda: GetResource('missing', HandleError=False))
rejects(SyntaxException, lambda: GetResource(42, HandleError=False))
rejects(SyntaxException, lambda: GetResource('value', 'extra', HandleError=False))
rejects(DriverException, lambda: GetResource('value', IsLocal=True, HandleError=False))
""", recovery="""
rejects(DriverException, lambda: GetResource('missing', HandleError=False))
assert SetResource('value', 21, HandleError=False) is True
equal(GetResource('value', HandleError=False), 21)
""")

group('resource-write', ['FUNCTION-SETRESOURCE', 'EXAMPLE-111'], positive="""
assert SetResource('value', 42, HandleError=False) is True
equal(GetResource('value', HandleError=False), 42)
equal(fixture('resource_state')['resources']['value'], 42)
""", boundary="""
for value in (0, False, '', [], {}, -(2**63), 2**63-1, 2.5, 'café λ', [False, {'items':[0, 1]}], {'PromptUser':'literal data','Wait':False}):
    assert SetResource('value', value, HandleError=False) is True
    equal(fixture('resource_state')['resources']['value'], value)
""", failure="""
before = fixture('resource_state')
rejects(DriverException, lambda: SetResource('missing-write', 99, HandleError=False))
equal(fixture('resource_state')['resources'], before['resources'])
rejects(SyntaxException, lambda: SetResource('value', HandleError=False))
rejects(SyntaxException, lambda: SetResource(42, 1, HandleError=False))
rejects(SyntaxException, lambda: SetResource('value', 99, 'extra', HandleError=False))
rejects(DriverException, lambda: SetResource('value', None, HandleError=False))
rejects(DriverException, lambda: SetResource('value', float('inf'), HandleError=False))
rejects(DriverException, lambda: SetResource('value', float('nan'), HandleError=False))
rejects(DriverException, lambda: SetResource('value', 'x' * 70000, HandleError=False))
for value in (-(2**63)-1, 2**63, {'nested':[2**63]}):
    rejects(DriverException, lambda: SetResource('value', value, HandleError=False))
plan_prompt(['SKIP','REPEAT','CANCEL','ABORT'], 'CANCEL')
equal(SetResource('value', {'nested':[2**63]}, OnFailure=SKIP|REPEAT|CANCEL|ABORT, PromptFailure=True), None)
rejects(DriverException, lambda: SetResource('value', 99, IsLocal=True, HandleError=False))
after = fixture('resource_state')
equal(after['resources'], before['resources'])
equal(after['effects'], before['effects'])
""", recovery="""
rejects(DriverException, lambda: SetResource('missing-write-again', 99, HandleError=False))
assert SetResource('value', 21, HandleError=False) is True
equal(GetResource('value', HandleError=False), 21)
equal(fixture('resource_state')['resources']['value'], 21)
""")

group('resource-mapping', ['EXAMPLE-113', 'EXAMPLE-140', 'EXAMPLE-141'], positive="""
GDB['DECODER'] = 'CMD_ACT_DEC'
GDB['DECODER 1'] = 'DEC1'
GDB['DECODER_CALIBRATION'] = {0:'DEC1', 1:'DEC2'}
assert SetResource(GDB['DECODER'], GDB['DECODER 1'], HandleError=False) is True
equal(fixture('resource_state')['resources']['CMD_ACT_DEC'], 'DEC1')
""", boundary="""
for index in (0, 1):
    value = GDB['DECODER_CALIBRATION'][index]
    assert SetResource(GDB['DECODER'], value, HandleError=False) is True
    equal(GetResource('CMD_ACT_DEC', HandleError=False), value)
    equal(fixture('resource_state')['resources']['CMD_ACT_DEC'], value)
""", failure="""
GDB['MISSING'] = 'missing-map'
before = fixture('resource_state')['resources']
rejects(DriverException, lambda: SetResource(GDB['MISSING'], 'DEC1', HandleError=False))
equal(fixture('resource_state')['resources'], before)
""", recovery="""
rejects(DriverException, lambda: GetResource(GDB['MISSING'], HandleError=False))
assert SetResource('CMD_ACT_DEC', 'DEC1', HandleError=False) is True
equal(GetResource(GDB['DECODER'], HandleError=False), GDB['DECODER_CALIBRATION'][0])
equal(fixture('resource_state')['resources']['CMD_ACT_DEC'], 'DEC1')
""")
