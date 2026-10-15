"""LRM p89: real child argument transfer and access, with separate failures."""
CASES = {}
PREFIX = '''import json
from pathlib import Path
from spell.lang.functions import StartProc
from spell.lib.exception import SyntaxException
rejections=0
'''
REJECT = '''for bad in ((), 'invalid', [['A']], [('A',1)]):
    try:
        StartProc('child', args=bad, HandleError=False)
    except SyntaxException:
        rejections+=1
    else:
        raise AssertionError('Malformed argument definitions accepted')
'''
CHILD_PREFIX = '''import json
from pathlib import Path
import builtins
assert not hasattr(builtins,'ARGS')
from spell.runtime import ARGS
'''


def case(group, dimension, arguments, child, expected, *, reject=False, launch=True):
    parent = PREFIX + (REJECT if reject else '')
    if launch:
        parent += f"assert StartProc('child', args={arguments}, HandleError=False) is True\n"
    parent += "Path('parent-result.json').write_text(json.dumps({'rejections':rejections}))\n"
    contracts = (['EXAMPLE-160', 'SYNTAX-PROCEDURE-ARGUMENT'] if group == 'arguments'
                 else ['EXAMPLE-161'])
    CASES[group+':'+dimension] = dict(
        dimension=dimension, contracts=['CMP-LRM244-'+name for name in contracts],
        oracle='LRM p89 Examples 160-161: original StartProc transfers argument pairs to the real child ARGS container; malformed definitions reject before opening a child and missing-key access fails independently.',
        parent=parent, child=CHILD_PREFIX+child,
        expected_parent={'rejections':4 if reject else 0},
        expected_child=expected, expected_children=int(launch))


PAIR = '''assert type(ARGS['A']) is int and ARGS['A']==1
assert type(ARGS['B']) is int and ARGS['B']==2
Path('child-result.json').write_text(json.dumps({'A':ARGS['A'],'B':ARGS['B']}))
'''
EMPTY = '''assert len(ARGS)==0
Path('child-result.json').write_text(json.dumps({'length':len(ARGS)}))
'''
MISSING = '''try:
    ARGS['MISSING']
except KeyError:
    missing=True
else:
    raise AssertionError('Missing argument did not raise KeyError')
'''
case('arguments','positive',"[['A',1],['B',2]]",PAIR,{'A':1,'B':2})
case('arguments','boundary','[]',EMPTY,{'length':0})
case('arguments','failure','[]',EMPTY,None,reject=True,launch=False)
case('arguments','recovery',"[['A',1],['B',2]]",PAIR,{'A':1,'B':2},reject=True)
case('access','positive',"[['A',1],['B',2]]",PAIR,{'A':1,'B':2})
case('access','boundary',"[['A',0],['B',False],['C','']]",'''assert type(ARGS['A']) is int and ARGS['A']==0
assert type(ARGS['B']) is bool and ARGS['B'] is False
assert type(ARGS['C']) is str and ARGS['C']==''
Path('child-result.json').write_text(json.dumps({'types':[type(ARGS[k]).__name__ for k in ('A','B','C')]}))
''',{'types':['int','bool','str']})
case('access','failure',"[['A',1]]",MISSING+"Path('child-result.json').write_text(json.dumps({'missing':missing}))\n",{'missing':True})
case('access','recovery',"[['A',1]]",MISSING+'''assert type(ARGS['A']) is int and ARGS['A']==1
Path('child-result.json').write_text(json.dumps({'missing':missing,'A':ARGS['A']}))
''',{'missing':True,'A':1})
