"""Native noninterleaved groups, single-frame blocks and truthful member status."""
from command_catalog_cases import HEADER

CASES={}
def add(name,body,executions,stages,loaded,members,*,clock=None):
    CASES[name]=dict(dimension=name.split(':')[1],source=HEADER+body+
        "\nPath('result.json').write_text(json.dumps({'completed':True}))\n",
        expected_executions=executions,expected_stages=stages,expected_loaded=loaded,
        expected_members=members,clock=clock)

add('API:positive',"from spell.lang.modifiers import Group\nassert Group=='Group'",0,0,0,[])
for mode in ('Group','Block'):
    blocked=mode=='Block'
    count=lambda n:1+4*n if blocked else 5*n
    add(mode+':positive',f"send(group=['CMD1','CMD3'],{mode}=True)",2,count(2),2,['CMD1','CMD3'])
    add(mode+':boundary',f"send(group=['CMD1','CMD1'],{mode}=True)",2,count(2),2,['CMD1','CMD1'])
    add(mode+':failure',f"send(False,group=['CMD1','TC.SIMULATOR.RESET','CMD3'],{mode}=True,ConfirmCritical=False)",
        1,7 if blocked else 8,3 if blocked else 2,['CMD1','TC.SIMULATOR.RESET','CMD3'] if blocked else ['CMD1','TC.SIMULATOR.RESET'])
    add(mode+':recovery',f"send(False,group=['CMD1','CMD3'],{mode}='invalid')\nsend(group=['CMD1','CMD3'],{mode}=True)",2,count(2),2,['CMD1','CMD3'])
    add(mode+':encoding',f"send(group=['CMD1','CMD3'],{mode}=True,addInfo={{'note':'café λ 遥測'}})",2,count(2),2,['CMD1','CMD3'])
    add(mode+'LoadOnly:positive',f"send(group=['CMD1','CMD3'],{mode}=True,LoadOnly=True)",0,3 if blocked else 4,2,['CMD1','CMD3'])
    add(mode+'Time:positive',f"from spell.lib.adapter.utctime import NOW,TIME\nsend(group=['CMD1','CMD3'],{mode}=True,Time=NOW+TIME('+00:00:00.35'))",
        2,count(2),2,['CMD1','CMD3'],clock='onboard')
    add(mode+'Sequence:positive',f"send(group=['SEQ.DUPLICATE','CMD3'],{mode}=True)",4,count(4),4,['CMD1','CMD1','CMD2','CMD3'])
