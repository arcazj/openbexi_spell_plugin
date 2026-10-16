"""LRM p83 typed keys and compound date/time values in actual database files."""
CASES={}


def add(family,dimension,source):
    CASES[family+'-'+dimension]=dict(dimension=dimension,source=source,contracts=[],
        oracle='Literal key/value types and retained file bytes through original native LoadDictionary and SaveDictionary')


add('keys','positive',r'''
path.write_text("42\t'integer'\n2.5\t'float'\n0xFF\t'hex'\n035\t'octal'\n0b101001\t'binary'\n",encoding='utf-8')
db=call(LoadDictionary,uri)
expected={42:'integer',2.5:'float',255:'hex',29:'octal',41:'binary'}
assert set(db.keys())==set(expected)
for key,value in expected.items():assert db[key]==value
assert call(SaveDictionary,db) is True
loaded=call(LoadDictionary,uri)
for key,value in expected.items():assert loaded[key]==value
''')
add('keys','boundary',r'''
db=call(CreateDictionary,uri)
values={0:'zero',-17:'negative',2**80:'large',0.25:'fraction',
        '42':'numeric text','two spaces':'spaced key','2007/01/23 10:30':'date text'}
for key,value in values.items():db[key]=value
assert call(SaveDictionary,db) is True
loaded=call(LoadDictionary,uri)
assert set(loaded.keys())==set(values)
for key,value in values.items():assert loaded[key]==value
''')
add('keys','failure',r'''
db=call(CreateDictionary,uri);db['KEY']=42;call(SaveDictionary,db)
before=path.read_bytes();keys=list(db.keys())
for bad in ([],{}):
    rejects(TypeError,lambda:db.__setitem__(bad,99))
    assert db.keys()==keys and path.read_bytes()==before
db[object()]=99
rejects(DriverException,lambda:call(SaveDictionary,db))
assert path.read_bytes()==before
''')
add('keys','recovery',r'''
db=call(CreateDictionary,uri);db['KEY']=42;call(SaveDictionary,db)
rejects(TypeError,lambda:db.__setitem__([],99))
db[17]='recovered'
assert call(SaveDictionary,db) is True
loaded=call(LoadDictionary,uri)
assert loaded['KEY']==42 and loaded[17]=='recovered' and len(loaded)==2
''')
add('nested-time','positive',r'''
db=call(CreateDictionary,uri)
absolute=TIME('2007-01-23 10:30:00.123456');relative=TIME('+2 03:04:05.000006')
db['VALUES']={'items':[absolute,{'relative':relative}],'plain':[False,0,'two  spaces']}
assert call(SaveDictionary,db) is True
loaded=call(LoadDictionary,uri)['VALUES']
assert isinstance(loaded['items'][0],TIME) and loaded['items'][0].value()==absolute.value()
assert isinstance(loaded['items'][1]['relative'],TIME) and loaded['items'][1]['relative'].value()==relative.value()
assert loaded['plain']==[False,0,'two  spaces']
''')
add('nested-time','boundary',r'''
db=call(CreateDictionary,uri)
db['VALUES']=[[],{},TIME('-0 00:00:00.000001'),TIME('+0 00:00:00'),{'literal':"TIME('not a timestamp')"}]
assert call(SaveDictionary,db) is True
loaded=call(LoadDictionary,uri)['VALUES']
assert loaded[:2]==[[],{}]
assert loaded[2].value()==TIME('-0 00:00:00.000001').value()
assert loaded[3].value()==TIME('+0 00:00:00').value()
assert loaded[4]=={'literal':"TIME('not a timestamp')"}
''')
add('nested-time','failure',r'''
db=call(CreateDictionary,uri);db['KEY']=42;call(SaveDictionary,db);before=path.read_bytes()
cyclic=[];cyclic.append(cyclic)
for value in (cyclic,{'bad':float('inf')},[object()]):
    db['VALUES']=value
    rejects(DriverException,lambda:call(SaveDictionary,db))
    assert path.read_bytes()==before and not list(path.parent.glob('.spell-db-*'))
''')
add('nested-time','recovery',r'''
db=call(CreateDictionary,uri);db['KEY']=42;call(SaveDictionary,db)
db['VALUES']=[object()]
rejects(DriverException,lambda:call(SaveDictionary,db))
db['VALUES']=[TIME('+0 00:00:35')]
assert call(SaveDictionary,db) is True
loaded=call(LoadDictionary,uri)
assert loaded['KEY']==42 and loaded['VALUES'][0].value()==TIME('+0 00:00:35').value()
''')
