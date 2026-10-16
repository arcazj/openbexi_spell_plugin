"""Complete positive/boundary/failure/recovery memory and catalog native forms."""
from memory_native_cases import CASES as BASELINE,HEADER

CASES=dict(BASELINE)
SUPPORT='''
import sqlite3
from contextlib import closing
def persisted():
    with closing(sqlite3.connect('driver.sqlite')) as db:
        ground=json.loads(db.execute('SELECT state FROM ground').fetchone()[0])
        effects=[tuple(v.hex() if type(v) is bytes else v for v in row)
                 for row in db.execute('SELECT * FROM effects ORDER BY request_id')]
        return ground,effects
def unchanged(operation):
    before=persisted()
    rejects(operation)
    equal(persisted(),before)
def skip(name,**options):
    row={'function':name,'policy':'SKIP','options':repr(options)}
    observed['calls'].append(row);save()
    value=getattr(api,name)(HandleError=True,PromptUser=False,PromptFailure=False,OnFailure=SKIP,**options)
    row.update(returned=repr(value),return_type=type(value).__name__);save()
    return value
def report(image='reference',destination='mem://voltage.txt',**options):
    return call('GenerateMemoryReport',Image=image,Type='TM',Source='GENERIC',Destination=destination,**options)
def compare(images,**options):
    return call('CompareMemoryImages',Image=images,Type='TM',Source='GENERIC',**options)
'''


def add(feature,dimension,body):
    name=feature+':'+dimension
    source=HEADER+SUPPORT+body+"\nFilePath('result.json').write_text(json.dumps({'completed':True}))\n"
    compile(source,name,'exec')
    CASES[name]=dict(feature=feature,dimension=dimension,source=source)


add('report','positive','''
golden(Type='TM')
equal(report(Begin='1',End='1',ValueFormat=RAW),True)
equal(FilePath('data/mem/voltage.txt').read_text(encoding='ascii'),'1\\tTM.POWER.BUS_VOLTAGE\\t28000\\n')
''')
add('report','boundary','''
golden(Type='TM')
equal(report(Begin='999',End='999'),True)
equal(FilePath('data/mem/voltage.txt').read_bytes()==b'',True)
equal(report(Begin='1',End='1'),True)
equal(FilePath('data/mem/voltage.txt').read_text(encoding='ascii'),'1\\tTM.POWER.BUS_VOLTAGE\\t28.0\\n')
''')
add('report','failure','''
golden(Type='TM')
FilePath('data/mem/preserved.txt').write_text('retained content')
unchanged(lambda:report(destination='mem://../escape'))
unchanged(lambda:report(image='missing',destination='mem://preserved.txt'))
unchanged(lambda:report(Begin='3',End='2'))
equal(FilePath('data/mem/preserved.txt').read_text(),'retained content')
equal(sorted(p.name for p in FilePath('data/mem').iterdir()),['preserved.txt'])
''')
add('report','recovery','''
unchanged(lambda:report(image='missing'))
golden(Type='TM')
equal(report(Begin='1',End='1',ValueFormat=RAW),True)
equal(FilePath('data/mem/voltage.txt').read_text(encoding='ascii'),'1\\tTM.POWER.BUS_VOLTAGE\\t28000\\n')
equal(sorted(p.name for p in FilePath('data/mem').iterdir()),['voltage.txt'])
''')
add('compare','positive','''
golden('first',Type='TM');golden('second',Type='TM')
equal(compare(['first','second']),True)
equal(compare(['first','first'],Begin='1',End='1'),True)
''')
add('compare','boundary','''
golden('first',Type='TM');fixture('step');golden('second',Type='TM')
equal(compare(['first','second'],Begin='1',End='1'),True)
equal(compare(['first','second'],Begin='6',End='6'),False)
equal(compare(['first','second'],Begin='999',End='999'),True)
''')
add('compare','failure','''
golden('first',Type='TM');golden('json',Type='JSON')
unchanged(lambda:compare(['first','missing']))
unchanged(lambda:compare(['first','first'],Begin='3',End='2'))
unchanged(lambda:compare(['first','json']))
''')
add('compare','recovery','''
unchanged(lambda:compare(['first','second']))
golden('first',Type='TM');golden('second',Type='TM')
equal(compare(['first','second']),True)
fixture('step');golden('second',Type='TM')
equal(compare(['first','second']),False)
''')
add('lookup','positive','''
golden(Type='TM')
equal(lookup(Name='TM.POWER.BUS_VOLTAGE',ValueFormat=RAW),{'TM.POWER.BUS_VOLTAGE':28000})
equal(lookup(Name='TM.POWER.BUS_VOLTAGE',ValueFormat=ENG),{'TM.POWER.BUS_VOLTAGE':28.0})
''')
add('lookup','boundary','''
golden(Type='TM')
equal(lookup(Address=1,ValueFormat=RAW),{'TM.POWER.BUS_VOLTAGE':28000})
equal(lookup(Name='',Begin='999',End='999'),{})
before=persisted()
equal(skip('MemoryLookup',Name='',Image='missing',Type='TM',Source='GENERIC'),None)
equal(persisted(),before)
''')
add('lookup','failure','''
golden(Type='TM')
unchanged(lambda:lookup(Address=999))
unchanged(lambda:lookup(Name='MISSING'))
unchanged(lambda:lookup(Name='',Begin='invalid',End='1'))
''')
add('lookup','recovery','''
unchanged(lambda:lookup(image='missing',Name='TM.POWER.BUS_VOLTAGE'))
golden(Type='TM')
equal(lookup(Name='TM.POWER.BUS_VOLTAGE'),{'TM.POWER.BUS_VOLTAGE':28.0})
''')
add('tmtc','positive','''
equal(call('TMTCLookup','TM.POWER.BUS_VOLTAGE',Type='TM',Source='GENERIC')['item_code'],1)
equal(call('TMTCLookup','CMD1',Type='TC',Source='GENERIC')['command_code'],2)
''')
add('tmtc','boundary','''
value=call('TMTCLookup','',Type='TC',Source='GENERIC',Begin='2',End='2')
equal(sorted(value),['CMD1']);equal(value['CMD1']['command_code'],2)
equal(call('TMTCLookup','CMD1',Type='TC',Source='GENERIC',Begin='3',End='4'),{})
before=persisted()
equal(skip('TMTCLookup',Name='MISSING',Type='TC',Source='GENERIC'),None)
equal(persisted(),before)
''')
add('tmtc','failure','''
unchanged(lambda:call('TMTCLookup','CMD1',Type='TC',Source='GENERIC',Begin='3',End='2'))
unchanged(lambda:call('TMTCLookup','CMD1',Type='UNKNOWN',Source='GENERIC'))
unchanged(lambda:call('TMTCLookup','CMD1',Type='TC',Source='MISSING'))
''')
add('tmtc','recovery','''
unchanged(lambda:call('TMTCLookup','MISSING',Type='TC',Source='GENERIC'))
equal(call('TMTCLookup','CMD1',Type='TC',Source='GENERIC')['effect'],'PAYLOAD_ON')
''')
