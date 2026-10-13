"""User database persistence examples, LRM pp81-84, actual native helpers."""
CASES = {}


def group(name, contracts, **dimensions):
    assert set(dimensions) == {'positive', 'boundary', 'failure', 'recovery'}
    for dimension, source in dimensions.items():
        CASES[name+':'+dimension] = dict(source=source, dimension=dimension,
            contracts=['CMP-LRM244-'+value for value in contracts],
            oracle='Original native executor and configured usr:// DatabaseFile; independent on-disk bytes, modes and directory entries observed with pathlib/os.')


group('create', ['EXAMPLE-144','SECTION-4-15-5-2-102'], positive=r"""
db=call(CreateDictionary,uri)
assert db.id()=='data.IMP' and len(db)==0 and path.read_bytes()==b''
db['KEY']=42
assert path.read_bytes()==b''
""", boundary=r"""
db=call(CreateDictionary,uri+'.custom')
assert (path.parent/'data.custom').is_file() and not path.exists()
assert len(db)==0
db=CreateDictionary(uri+'configured',{'Notify':False},HandleError=False)
assert len(db)==0 and (path.parent/'dataconfigured.IMP').is_file()
""", failure=r"""
path.write_bytes(b'SAVED 42\n')
db=call(LoadDictionary,uri)
db['UNSAVED']=99
rejects(DriverException,lambda:call(CreateDictionary,uri))
assert path.read_bytes()==b'SAVED 42\n' and db['UNSAVED']==99
for bad in ('bad name','../escape','/absolute','bad//name',''):
    rejects(SyntaxException,lambda:call(CreateDictionary,'usr://'+bad))
rejects(SyntaxException,lambda:call(CreateDictionary,uri+'extra','extra'))
path.parent.chmod(0o500)
try: rejects(DriverException,lambda:call(CreateDictionary,uri+'denied'))
finally: path.parent.chmod(0o700)
assert not (path.parent/'datadenied.IMP').exists()
""", recovery=r"""
path.write_bytes(b'SAVED 42\n')
rejects(DriverException,lambda:call(CreateDictionary,uri))
db=call(CreateDictionary,uri+'new')
db['KEY']=7
assert call(SaveDictionary,db) is True
assert call(LoadDictionary,uri+'new')['KEY']==7
assert path.read_bytes()==b'SAVED 42\n'
""")

group('load', ['EXAMPLE-143','SECTION-4-15-5-1-101'], positive=r"""
path.write_text("KEY 42\nTEXT 'caf\u00e9'\n",encoding='utf-8')
db=call(LoadDictionary,uri)
assert db['KEY']==42 and db['TEXT']=='caf\u00e9'
""", boundary=r"""
path.write_bytes(b'')
assert len(call(LoadDictionary,uri))==0
path.write_text("VALUE {'items':[0,False,[],{}]}\n",encoding='utf-8')
assert call(LoadDictionary,uri)['VALUE']=={'items':[0,False,[],{}]}
""", failure=r"""
rejects(DriverException,lambda:call(LoadDictionary,uri))
assert not path.exists()
rejects(SyntaxException,lambda:call(LoadDictionary,42))
rejects(SyntaxException,lambda:call(LoadDictionary,uri,'extra'))
""", recovery=r"""
rejects(DriverException,lambda:call(LoadDictionary,uri))
path.write_bytes(b'KEY 7\n')
assert call(LoadDictionary,uri)['KEY']==7
""")

group('save', ['EXAMPLE-145','SECTION-4-15-5-3-103'], positive=r"""
db=call(CreateDictionary,uri)
db['KEY']=42
assert path.read_bytes()==b''
assert call(SaveDictionary,db) is True
assert path.read_bytes()==b'KEY\t42\n'
assert call(LoadDictionary,uri)['KEY']==42
""", boundary=r"""
db=call(CreateDictionary,uri)
values={'ZERO':0,'FALSE':False,'EMPTY':'','LIST':[],'DICT':{},'BIG':2**80,
        'FLOAT':-2.5,'TEXT':' caf\u00e9  "quoted" '+chr(92)+'slash\nsecond line ',
        'NESTED':{'items':[False,0,'two  spaces']},'NONE':None}
for key,value in values.items(): db[key]=value
db['ABS']=TIME('2007-01-23 10:30:00.123456')
db['REL']=TIME('-0 00:00:00.000001')
path.chmod(0o640)
assert call(SaveDictionary,db) is True
assert path.stat().st_mode & 0o777 == 0o640
loaded=call(LoadDictionary,uri)
for key,value in values.items():
    assert loaded[key]==value and type(loaded[key]) is type(value),(key,loaded[key],value)
assert loaded['ABS'].value()==TIME('2007-01-23 10:30:00.123456').value()
assert loaded['REL'].value()==TIME('-0 00:00:00.000001').value()
assert not list(path.parent.glob('.spell-db-*'))
""", failure=r"""
path.write_bytes(b'KEY 42\n')
db=call(LoadDictionary,uri)
db.set('KEY','not an integer',HEX)
before=path.read_bytes()
rejects(DriverException,lambda:call(SaveDictionary,db))
assert path.read_bytes()==before and not list(path.parent.glob('.spell-db-*'))
db=call(LoadDictionary,uri)
for key,value in [('#lost',1),('NONFINITE',float('nan')),('NESTED',{'bad':float('inf')}),('OBJECT',object())]:
    db[key]=value
    rejects(DriverException,lambda:call(SaveDictionary,db))
    assert path.read_bytes()==before and not list(path.parent.glob('.spell-db-*'))
    del db[key]
cyclic=[]
cyclic.append(cyclic)
db['CYCLE']=cyclic
rejects(DriverException,lambda:call(SaveDictionary,db))
assert path.read_bytes()==before
del db['CYCLE']
path.chmod(0o400)
try: rejects(DriverException,lambda:call(SaveDictionary,db))
finally: path.chmod(0o600)
assert path.read_bytes()==before
rejects(SyntaxException,lambda:call(SaveDictionary,db,'extra'))
path.unlink()
rejects(DriverException,lambda:call(SaveDictionary,db))
assert not path.exists()
""", recovery=r"""
path.write_bytes(b'KEY 42\n')
db=call(LoadDictionary,uri)
db.set('KEY','bad',HEX)
rejects(DriverException,lambda:call(SaveDictionary,db))
db=call(LoadDictionary,uri)
db['KEY']=17
assert call(SaveDictionary,db) is True
assert call(LoadDictionary,uri)['KEY']==17
""")

group('revert', ['EXAMPLE-146','SECTION-4-15-5-4-104'], positive=r"""
path.write_text("KEY {'items':[1,2]}\n",encoding='utf-8')
before=path.read_bytes()
db=call(LoadDictionary,uri)
db['KEY']['items'][0]=99
db['NEW']='unsaved'
assert path.read_bytes()==before
db=call(LoadDictionary,uri)
assert db['KEY']=={'items':[1,2]} and not db.has_key('NEW')
""", boundary=r"""
path.write_bytes(b'')
db=call(LoadDictionary,uri)
db['KEY']=False
assert path.read_bytes()==b''
assert len(call(LoadDictionary,uri))==0
""", failure=r"""
path.write_bytes(b'KEY 42\n')
db=call(LoadDictionary,uri)
db['KEY']=99
path.unlink()
rejects(DriverException,lambda:call(LoadDictionary,uri))
assert db['KEY']==99
""", recovery=r"""
path.write_bytes(b'KEY 42\n')
db=call(LoadDictionary,uri)
db['KEY']=99
path.unlink()
rejects(DriverException,lambda:call(LoadDictionary,uri))
path.write_bytes(b'KEY 7\n')
assert call(LoadDictionary,uri)['KEY']==7
""")

group('formats', ['EXAMPLE-147','EXAMPLE-148'], positive=r"""
path.write_text(EXAMPLE,encoding='utf-8')
db=call(LoadDictionary,uri)
assert db['KEY1']==45.67
assert db['KEY2']=='This is a string'
assert db['KEY3']=='This is another string'
assert db['KEY4'].value()==TIME('2007/01/23 10:30').value()
assert db['KEY5']==0b011001
assert db['KEY6']==[0,1,2,3,4] and db['KEY6'][1]==1
assert db['KEY7']=={'A':24,'B':34,'C':['X','Y','Z']} and db['KEY7']['C'][2]=='Z'
assert call(SaveDictionary,db) is True
assert 'KEY5\t0b011001\n' in path.read_text(encoding='utf-8')
db=call(LoadDictionary,uri)
assert db['KEY4'].value()==TIME('2007/01/23 10:30').value() and db['KEY7']['C'][2]=='Z'
""", boundary=r"""
path.write_text("TEXT '  two  spaces  '\nHEX 0x00\nBIN 0b000000\nREL -0 00:00:00.000001\n",encoding='utf-8')
db=call(LoadDictionary,uri)
assert db['TEXT']=='  two  spaces  ' and db['HEX']==0 and db['BIN']==0
assert call(SaveDictionary,db) is True
assert 'BIN\t0b000000\n' in path.read_text(encoding='utf-8')
db=call(LoadDictionary,uri)
assert db['REL'].value()==TIME('-0 00:00:00.000001').value()
""", failure=r"""
path.write_text(EXAMPLE,encoding='utf-8')
db=call(LoadDictionary,uri)
rejects(DriverException,lambda:db['MISSING'])
rejects(IndexError,lambda:db['KEY6'][99])
rejects(KeyError,lambda:db['KEY7']['MISSING'])
before=path.read_bytes()
db.set('KEY5','not a number',BIN+'6')
rejects(DriverException,lambda:call(SaveDictionary,db))
assert path.read_bytes()==before
""", recovery=r"""
path.write_text(EXAMPLE,encoding='utf-8')
db=call(LoadDictionary,uri)
db.set('KEY5','bad',BIN+'6')
rejects(DriverException,lambda:call(SaveDictionary,db))
db=call(LoadDictionary,uri)
db['KEY7']['C'][2]='recovered'
assert call(SaveDictionary,db) is True
assert call(LoadDictionary,uri)['KEY7']['C'][2]=='recovered'
""")

EXAMPLE = """KEY1 45.67
KEY2 This is a string
KEY3 'This is another string'
KEY4 2007/01/23 10:30
KEY5 0b011001
KEY6 [0,1,2,3,4]
KEY7 {'A':24, 'B':34, 'C':['X','Y','Z']}
"""
