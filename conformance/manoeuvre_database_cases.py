"""LRM p79: configured manoeuvre locations and read-only database objects."""
from memory_native_cases import HEADER

PRELUDE='''
from spell.lib.exception import SyntaxException
import os
target=FilePath(os.environ['SPELL_DATA'])/'ManeuverDB/Man01/Part1.IMP'
target.parent.mkdir(parents=True,exist_ok=True)
uri='mmd://Man01/Part1'
def seed(text="KEY 42\\nNESTED {'items':[0,False,'text']}\\n"):
    target.write_text(text,encoding='utf-8')
def syntax_error(operation):
    try:operation()
    except SyntaxException:pass
    else:raise AssertionError('Expected SyntaxException')
'''
CASES={}
def add(feature,dimension,body):
    CASES[feature+'-'+dimension]=dict(dimension=dimension,
        source=HEADER+PRELUDE+body+"\nFilePath('result.json').write_text(json.dumps({'completed':True}))\n")

add('load','positive','''
seed()
database=call('LoadDictionary',uri)
equal(database['KEY'],42)
equal(database['NESTED']['items'],[0,False,'text'])
equal(database.has_key('KEY'),True)
equal(database.id(),'Part1.IMP')
''')
add('load','boundary','''
seed('')
equal(len(call('LoadDictionary',uri)),0)
alternate=target.with_name('Part2.custom')
alternate.write_text("OCTAL 035\\nHEX 0xFF\\nTEXT 'two  spaces'\\n",encoding='utf-8')
database=call('LoadDictionary','mmd://Man01/Part2.custom')
equal(database['OCTAL'],29)
equal(database['HEX'],255)
equal(database['TEXT'],'two  spaces')
''')
add('load','failure','''
rejects(lambda:call('LoadDictionary',uri))
equal(target.exists(),False)
syntax_error(lambda:call('LoadDictionary','mmd://../escape'))
equal(list(target.parent.iterdir()),[])
''')
add('load','recovery','''
rejects(lambda:call('LoadDictionary',uri))
seed('KEY 7\\n')
equal(call('LoadDictionary',uri)['KEY'],7)
''')
add('readonly','positive','''
seed()
database=call('LoadDictionary',uri)
before=target.read_bytes()
rejects(lambda:database.__setitem__('KEY',99))
rejects(lambda:database.__delitem__('KEY'))
rejects(lambda:database.set('KEY',99))
equal(database['KEY'],42)
equal(target.read_bytes()==before,True)
''')
add('readonly','boundary','''
seed()
database=call('LoadDictionary',uri)
detached=database['NESTED'];detached['items'].append('changed')
equal(database['NESTED']['items'],[0,False,'text'])
keys=database.keys();keys.append('invented')
equal(database.has_key('invented'),False)
equal(len(database),2)
''')
add('readonly','failure','''
seed()
database=call('LoadDictionary',uri)
before=target.read_bytes()
rejects(lambda:call('SaveDictionary',database))
rejects(lambda:call('CreateDictionary','mmd://Man01/Prohibited'))
equal(target.read_bytes()==before,True)
equal((target.parent/'Prohibited.IMP').exists(),False)
''')
add('readonly','recovery','''
seed()
database=call('LoadDictionary',uri)
saved=target.with_suffix('.retained')
target.replace(saved)
try:
    rejects(database.reload)
    equal(database['KEY'],42)
finally:saved.replace(target)
seed('KEY 7\\n')
database.reload()
equal(database['KEY'],7)
rejects(lambda:database.__setitem__('KEY',9))
equal(database['KEY'],7)
''')
