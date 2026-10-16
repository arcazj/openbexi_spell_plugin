"""Native telemetry acceptance dimensions, with literal observed expectations."""
from telemetry_surface_cases import HEADER

CASES = {}


def add(feature, dimension, body, **options):
    CASES[feature+':'+dimension] = dict(feature=feature, dimension=dimension,
        source=HEADER+body+"\nFilePath('result.json').write_text(json.dumps({'completed':True}))\n", **options)


GET = "call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False)"

add('quality', 'positive', 'equal('+GET+',28.0)')
add('quality', 'boundary', '''
for quality in ('SUSPECT','UNKNOWN'):
    fixture('reset',faults={'telemetry_quality':quality})
    rejects(lambda:call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False))
''')
add('quality', 'failure', 'rejects(lambda:'+GET+')', faults={'telemetry_quality':'BAD'})
add('quality', 'recovery', "rejects(lambda:"+GET+")\nfixture('reset',faults={})\nequal("+GET+",28.0)", faults={'telemetry_quality':'BAD'})

add('validity', 'positive', 'equal('+GET+',28.0)')
add('validity', 'boundary', '''
fixture('reset',faults={'telemetry_validity':'INVALID'})
rejects(lambda:call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False,ValueFormat=RAW))
''')
add('validity', 'failure', 'rejects(lambda:'+GET+')', faults={'telemetry_validity':'INVALID'})
add('validity', 'recovery', "rejects(lambda:"+GET+")\nfixture('reset',faults={})\nequal("+GET+",28.0)", faults={'telemetry_validity':'INVALID'})

add('freshness', 'positive', 'equal('+GET+',28.0)')
add('freshness', 'boundary', '''
fixture('reset',faults={})
time.sleep(3.5)
equal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False),28.0)
time.sleep(2.5)
rejects(lambda:call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False))
''')
add('freshness', 'failure', 'rejects(lambda:'+GET+')', faults={'stale':True})
add('freshness', 'recovery', "rejects(lambda:"+GET+")\nfixture('reset',faults={})\nequal("+GET+",28.0)", faults={'stale':True})

add('availability', 'positive', 'equal('+GET+',28.0)')
add('availability', 'boundary', '''
rejects(lambda:call('GetTM','TM.ABSENT',Wait=False))
equal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False),28.0)
''')
add('availability', 'failure', 'rejects(lambda:'+GET+')', faults={'missing_items':['TM.POWER.BUS_VOLTAGE']})
add('availability', 'recovery', "rejects(lambda:"+GET+")\nfixture('reset',faults={})\nequal("+GET+",28.0)", faults={'missing_items':['TM.POWER.BUS_VOLTAGE']})

add('link', 'positive', "fixture('link',enabled=True)\nequal("+GET+",28.0)")
add('link', 'boundary', "fixture('link',enabled=False)\nfixture('link',enabled=False)\nrejects(lambda:"+GET+")")
add('link', 'failure', "fixture('link',enabled=False)\nrejects(lambda:"+GET+")")
add('link', 'recovery', "fixture('link',enabled=False)\nrejects(lambda:"+GET+")\nfixture('link',enabled=True)\nequal("+GET+",28.0)")

add('minute', 'positive', '''
fixture('feed',enabled=True,delay=36)
started=time.monotonic()
equal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=True,Timeout=1*MINUTE),28.0)
elapsed=time.monotonic()-started
observed['observations'].append({'acquisition_elapsed':elapsed});save()
assert 35<=elapsed<45,elapsed
''')
add('minute', 'boundary', '''
fixture('feed',enabled=True)
equal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=True,Timeout=3600),28.0)
rejects(lambda:call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=True,Timeout=3600.001))
''')
add('minute', 'failure', '''
for value in (0,-1,True,float('inf')):
    rejects(lambda:call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=True,Timeout=value))
''')
add('minute', 'recovery', '''
rejects(lambda:call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=True,Timeout=.1))
fixture('feed',enabled=True)
equal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=True,Timeout=1*MINUTE),28.0)
''')

PRINT = '''
for name in result.keys():
    line=name+' : '+str(result[name])
    api.Display(line)
    observed['observations'].append({'displayed':line});save()
'''
for dimension, values, expected in (
    ('positive', "[['TM.POWER.BUS_VOLTAGE',eq,28.0],['TM.THERMAL.MODE',eq,'OFF']]", [True,True]),
    ('boundary', "[['TM.POWER.BUS_VOLTAGE',eq,28.0],['TM.POWER.BUS_VOLTAGE',eq,27.0]]", [True,False]),
    ('failure', "[['TM.POWER.BUS_VOLTAGE',eq,27.0],['TM.THERMAL.MODE',eq,'wrong']]", [False,False]),
    ('recovery', "[['TM.POWER.BUS_VOLTAGE',eq,28.0],['TM.THERMAL.MODE',eq,'OFF']]", [True,True]),
):
    prefix = "rejects(lambda:call('GetTM','TM.ABSENT',Wait=False))\n" if dimension == 'recovery' else ''
    add('printed', dimension, prefix+"result=call('Verify',"+values+",Wait=False,Retries=0,OnFalse=NOACTION)\n"+
        'equal([result[name] for name in result.keys()],'+repr(expected)+')\n'+PRINT)

add('between-list', 'positive', '''
equal(bool(call('Verify',['TM.POWER.BUS_VOLTAGE',bw,27,29],Wait=False,Retries=0,Tolerance=0,OnFalse=NOACTION)),True)
''')
add('between-list', 'boundary', '''
fixture('feed',enabled=True)
for strict,wanted in [(False,True),(True,False)]:
    for operator in (bw,nbw):
        equal(bool(call('Verify',['TM.POWER.BUS_VOLTAGE',operator,28,28],Wait=False,Retries=0,Tolerance=0,Strict=strict,OnFalse=NOACTION)),wanted)
''')
add('between-list', 'failure', '''
rejects(lambda:call('Verify',['TM.POWER.BUS_VOLTAGE',bw,'27',29],Wait=False,Retries=0,Tolerance=0,OnFalse=NOACTION))
''')
add('between-list', 'recovery', '''
rejects(lambda:call('Verify',['TM.POWER.BUS_VOLTAGE',bw,'27',29],Wait=False,Retries=0,Tolerance=0,OnFalse=NOACTION))
equal(bool(call('Verify',['TM.POWER.BUS_VOLTAGE',nbw,29,30],Wait=False,Retries=0,Tolerance=0,OnFalse=NOACTION)),True)
''')
