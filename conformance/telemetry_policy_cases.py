"""Original GetTM failure actions under real bad-quality telemetry."""
from telemetry_surface_cases import HEADER

POLICY = '''
row={'function':'GetTM','args':"('TM.POWER.BUS_VOLTAGE',)",'options':'interactive ABORT|SKIP|REPEAT'}
observed['calls'].append(row);save()
value=api.GetTM('TM.POWER.BUS_VOLTAGE',Wait=False,HandleError=True,
                PromptUser=True,PromptFailure=True,OnFailure=ABORT|SKIP|REPEAT)
row.update(returned=repr(value),return_type=type(value).__name__);save()
'''
CASES = {}
for dimension,actions,repair_after,status,body in (
    ('positive',['REPEAT'],1,'FINISHED','equal(value,28.0)'),
    ('boundary',['REPEAT','REPEAT'],2,'FINISHED','equal(value,28.0)'),
    ('failure',['ABORT'],None,'ABORTED',"raise AssertionError('ABORT returned to caller')"),
    ('recovery',['SKIP'],None,'FINISHED',
     "equal(value,None)\nfixture('reset',faults={})\nequal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False),28.0)"),
):
    CASES['failure-policy:'+dimension] = dict(feature='failure-policy',dimension=dimension,
        source=HEADER+POLICY+body+"\nFilePath('result.json').write_text(json.dumps({'completed':True}))\n",
        faults={'telemetry_quality':'UNKNOWN' if dimension=='boundary' else 'BAD'},
        actions=actions,repair_after=repair_after,expected_status=status)
