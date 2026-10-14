"""Named runtime SCDB policy, real original backend and native startup."""
CASES = {}
SCDB = "SC 'Test spacecraft'\nSpacecraft_Name 'Test spacecraft'\nZERO 0\nFALSE False\nEMPTY ''\nNESTED {'items':[1,{'flag':False}]}\n"
GDB = "GROUND 'mutable'\n"
ROWS = ['CMP-LRM244-DATABASE-SCDB', 'CMP-LRM244-SECTION-4-15-1-096']


def add(name, dimension, source, spacecraft=SCDB, fresh=None):
    CASES[name] = dict(dimension=dimension, contracts=ROWS, source=source,
        spacecraft=spacecraft, ground=GDB, fresh_source=fresh,
        oracle='Original native startup installs named SCDB through the actual DBMGR; public writes fail without memory/file effects, detached values/keys preserve read-only state, real backend refresh recovers, GDB/user databases stay writable.')


add('read:positive', 'positive', '''
from spell.lib.adapter.databases.database import Database
from spell.lib.registry import REGISTRY
assert isinstance(SCDB, Database)
assert REGISTRY['DBMGR']['SCDB'] is SCDB
assert SCDB['SC'] == 'Test spacecraft'
assert SCDB.get('SC') == 'Test spacecraft' and SCDB.get('missing') is None
assert SCDB.has_key('Spacecraft_Name') is True and SCDB.has_key('missing') is False
assert SCDB.keys() == ['SC','Spacecraft_Name','ZERO','FALSE','EMPTY','NESTED']
assert len(SCDB) == 6 and bool(SCDB) is True
assert SCDB.id() == 'SCDB.DB'
assert "'SC' = 'Test spacecraft'" in repr(SCDB)
assert SCDB['ZERO'] == 0 and type(SCDB['ZERO']) is int
assert SCDB['FALSE'] is False and SCDB['EMPTY'] == ''
''')
add('read:empty', 'boundary', '''
assert len(SCDB) == 0 and bool(SCDB) is False
assert SCDB.keys() == [] and repr(SCDB) == '{}'
assert SCDB.get('missing') is None and SCDB.has_key('missing') is False
rejects(DriverException, lambda: SCDB['missing'])
''', spacecraft='# empty spacecraft database\n')
add('read:invalid-recovery', 'recovery', '''
rejects(DriverException, lambda: SCDB['missing'])
rejects(TypeError, lambda: SCDB[[]])
rejects(TypeError, lambda: SCDB.keys('extra'))
rejects(TypeError, lambda: SCDB.has_key())
assert SCDB['SC'] == 'Test spacecraft'
''')
for name, operation in {
    'assignment-existing':"SCDB.__setitem__('SC','changed')",
    'assignment-new':"SCDB.__setitem__('NEW',1)",
    'set-existing':"SCDB.set('SC','changed')",
    'set-new-format':"SCDB.set('NEW',255,'hex')",
    'delete-existing':"SCDB.__delitem__('SC')",
    'delete-missing':"SCDB.__delitem__('missing')",
    'create':"SCDB.create()",
    'commit':"SCDB.commit()",
    'save-dictionary':"SaveDictionary(SCDB,HandleError=False)",
    'manager-create':"REGISTRY['DBMGR'].createDatabase('SCDB')",
}.items():
    add('write:'+name, 'failure', 'unchanged(lambda: '+operation+')')
add('write:save-policy', 'failure', '''
from spell.lang.constants import CANCEL
before = snapshot()
assert SaveDictionary(SCDB, OnFailure=CANCEL, PromptFailure=False) is False
assert snapshot() == before
''')
add('read:detached', 'boundary', '''
expected = {'items':[1,{'flag':False}]}
first = SCDB['NESTED']
second = SCDB.get('NESTED')
assert first == second == expected and first is not second
first['items'][1]['flag'] = True
second['items'].append('changed')
keys = SCDB.keys()
keys[:] = ['changed']
assert SCDB['NESTED'] == expected and SCDB.get('NESTED') == expected
assert SCDB.keys() == ['SC','Spacecraft_Name','ZERO','FALSE','EMPTY','NESTED']
''')
add('reload:positive', 'positive', '''
ask('replace', "SC 'External update'\\nZERO 2\\n")
assert SCDB['SC'] == 'Test spacecraft'
assert SCDB.reload() is None
assert SCDB['SC'] == 'External update' and SCDB['ZERO'] == 2
assert SCDB.keys() == ['SC','ZERO']
unchanged(lambda: SCDB.set('SC','changed'))
''')
add('read:detached-item', 'boundary', '''
value = SCDB['NESTED']
value['items'][1]['flag'] = True
assert SCDB['NESTED'] == {'items':[1,{'flag':False}]}, repr(SCDB['NESTED'])
''')
add('read:detached-get', 'boundary', '''
value = SCDB.get('NESTED')
value['items'].append('changed')
assert SCDB.get('NESTED') == {'items':[1,{'flag':False}]}, repr(SCDB.get('NESTED'))
''')
add('read:detached-keys', 'boundary', '''
keys = SCDB.keys()
keys[:] = ['changed']
assert SCDB.keys() == ['SC','Spacecraft_Name','ZERO','FALSE','EMPTY','NESTED'], repr(SCDB.keys())
assert SCDB.has_key('SC') is True
''')
add('load:boundary', 'boundary', '''
ask('replace', '# externally emptied file\\n')
assert SCDB.load() is None and not SCDB
assert SCDB.keys() == []
unchanged(lambda: SCDB.__setitem__('NEW',1))
''')
add('reload:failure-recovery', 'recovery', '''
before = snapshot()
ask('remove')
rejects(DriverException, SCDB.reload)
assert snapshot() == before
ask('invalid-utf8')
rejects(DriverException, SCDB.load)
assert snapshot() == before
ask('replace', "SC 'Recovered'\\nNESTED {'items':[2,{'flag':True}]}\\n")
assert SCDB.reload() is None
assert SCDB['SC'] == 'Recovered' and SCDB['NESTED']['items'][0] == 2
unchanged(lambda: SCDB.__delitem__('SC'))
''')
add('manager:recovery', 'recovery', '''
assert REGISTRY['DBMGR'].createEmptyDatabase('SCDB') is SCDB
assert REGISTRY['DBMGR'].loadDatabase('SCDB') is SCDB
unchanged(lambda: REGISTRY['DBMGR']['SCDB'].create())
assert SCDB['SC'] == 'Test spacecraft'
''')
add('ground:mutable', 'positive', '''
GDB['GROUND'] = 'updated'
GDB.set('COUNT',3)
GDB['DELETE'] = True
del GDB['DELETE']
assert SaveDictionary(GDB,HandleError=False) is True
GDB.reload()
assert GDB['GROUND'] == 'updated' and GDB['COUNT'] == 3
assert not GDB.has_key('DELETE')
assert SCDB['SC'] == 'Test spacecraft'
''', fresh="assert GDB['GROUND'] == 'updated' and GDB['COUNT'] == 3; assert not GDB.has_key('DELETE')")
add('user:mutable', 'recovery', '''
db = CreateDictionary('usr://writable',HandleError=False)
db['VALUE'] = 7
db.set('TEXT','writable')
db['DELETE'] = 8
del db['DELETE']
assert SaveDictionary(db,HandleError=False) is True
loaded = LoadDictionary('usr://writable',HandleError=False)
assert loaded['VALUE'] == 7 and loaded['TEXT'] == 'writable'
assert not loaded.has_key('DELETE')
unchanged(lambda: SCDB.commit())
''', fresh="db=LoadDictionary('usr://writable',HandleError=False); assert db['VALUE'] == 7 and db['TEXT'] == 'writable'; assert not db.has_key('DELETE')")
