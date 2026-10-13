"""Bounded composed telemetry timing baseline; no coverage promotion."""
CASES = {}
METADATA = {}
def add(name, code):
    CASES[name] = code
    METADATA[name] = {'dimension':name.rsplit(':',1)[-1], 'contracts':[], 'oracle':'Actual original native scheduling and DSS binary receipts; exploratory scope, no row promotion.'}

add('send-wait:positive', """
expected=fresh_setup();before=mark()
assert Send(command='CMD1',verify=[['TM.CORE.TICK',eq,expected]],config=dict(CFG,Wait=True,Timeout=2,Delay=0))
effects(before,['CMD1']);fresh_assert(expected)
""")
add('send-wait:boundary', """
fixture('feed',value=False);fixture('tick');before=mark()
assert Send(command='CMD2',verify=[['TM.POWER.BUS_VOLTAGE',eq,28.0]],config=dict(CFG,Wait=False,Timeout=.25,Delay=0))
effects(before,['CMD2']);equal(acquisition_waits(),[False])
""")
add('send-delay:positive', """
before=mark();began=time.monotonic()
assert Send(command='CMD1',verify=[['TM.POWER.BUS_VOLTAGE',eq,28.0]],config=dict(CFG,Wait=False,Timeout=2,Delay=1.25))
effects(before,['CMD1']);equal(acquisition_waits(),[False])
rows=mark()['rpc'];send=[r for r in rows if r['check']=='send-delay:positive' and r['path'].endswith('/SendCommand')]
assert len(send)==1,send
assert acquisitions()[0]['started'] >= send[0]['started']+send[0]['seconds']+1.20,(send,acquisitions())
""")
add('waitfor-wait:positive', """
expected=fresh_setup();before=mark()
assert WaitFor(['TM.CORE.TICK',eq,expected],Wait=True,Timeout=2,Delay=4,PromptUser=False,HandleError=False)
effects(before,[]);fresh_assert(expected)
""")
add('waitfor-wait:boundary', """
fixture('feed',value=False);fixture('tick');before=mark()
assert WaitFor(['TM.POWER.BUS_VOLTAGE',eq,28.0],Wait=False,Timeout=.25,Delay=2,PromptUser=False,HandleError=False)
effects(before,[]);equal(acquisition_waits(),[False])
""")
add('waitfor-delay:failure', """
before=mark();began=time.monotonic()
assert WaitFor(['TM.POWER.BUS_VOLTAGE',eq,0.0],Wait=False,Timeout=.25,Delay=1.25,PromptUser=False,HandleError=False) is False
assert 1.20<=time.monotonic()-began<8
assert len(acquisitions())>=2;assert not any(acquisition_waits());effects(before,[])
""")
add('waitfor-delay:recovery', """
before=mark()
assert WaitFor(['TM.POWER.BUS_VOLTAGE',eq,28.0],Wait=False,Timeout=.25,Delay=2,PromptUser=False,HandleError=False)
effects(before,[]);equal(acquisition_waits(),[False])
""")

add('send-wait:failure', """
fixture('feed',value=False);fixture('tick');before=mark()
rejects(DriverException,lambda:Send(command='CMD2',verify=[['TM.POWER.BUS_VOLTAGE',eq,28.0]],config=dict(CFG,Wait=True,Timeout=.3)))
effects(before,['CMD2']);equal(acquisition_waits(),[True]);equal(len(acquisitions()),1)
assert 'error' in acquisitions()[0];assert acquisitions()[0]['seconds']>=.25
""")
add('send-wait:recovery', """
expected=fresh_setup();before=mark()
assert Send(command='CMD1',verify=[['TM.CORE.TICK',eq,expected]],config=dict(CFG,Wait=True,Timeout=2))
effects(before,['CMD1']);fresh_assert(expected)
""")
add('waitfor-wait:failure', """
fixture('feed',value=False);fixture('tick');before=mark()
rejects(DriverException,lambda:WaitFor(['TM.POWER.BUS_VOLTAGE',eq,28.0],Wait=True,Timeout=.3,Delay=4,PromptUser=False,HandleError=False))
effects(before,[]);equal(acquisition_waits(),[True]);equal(len(acquisitions()),1)
assert 'error' in acquisitions()[0];assert acquisitions()[0]['seconds']>=.25
""")
add('waitfor-wait:recovery', """
expected=fresh_setup();before=mark()
assert WaitFor(['TM.CORE.TICK',eq,expected],Wait=True,Timeout=2,Delay=4,PromptUser=False,HandleError=False)
effects(before,[]);fresh_assert(expected)
""")
add('send-wait-override:boundary', """
fixture('feed',value=False);tick=fixture('tick')['state']['core']['tick'];before=mark()
config=dict(CFG,Wait=True,Timeout=2)
condition=['TM.CORE.TICK',eq,tick,{Wait:False,Timeout:.3}]
import copy
original=copy.deepcopy((config,condition))
assert Send(command='CMD1',verify=[condition],config=config)
effects(before,['CMD1']);equal(acquisition_waits(),[False]);equal(acquisition_configs()[0][Timeout],.3)
equal((config,condition),original)
""")
add('waitfor-wait-override:boundary', """
fixture('feed',value=False);tick=fixture('tick')['state']['core']['tick'];before=mark()
assert WaitFor(['TM.CORE.TICK',eq,tick,{Wait:False,Timeout:.3}],Wait=True,Timeout=2,Delay=3,PromptUser=False,HandleError=False)
effects(before,[]);equal(acquisition_waits(),[False]);equal(acquisition_configs()[0][Timeout],.3)
""")
add('send-false:failure', """
before=mark()
assert not Send(command='CMD1',verify=[['TM.POWER.BUS_VOLTAGE',eq,-999,{Retries:0}]],config=dict(CFG,Wait=False,Timeout=2,OnFalse=NOACTION))
effects(before,['CMD1']);equal(acquisition_waits(),[False])
""")
add('send-false:recovery', """
before=mark()
assert Send(command='CMD2',verify=[['TM.POWER.BUS_VOLTAGE',eq,28.0,{Retries:0}]],config=dict(CFG,Wait=False,Timeout=2))
effects(before,['CMD2']);equal(acquisition_waits(),[False])
""")
add('send-delay:boundary', """
before=mark()
assert Send(command='CMD2',verify=[['TM.POWER.BUS_VOLTAGE',eq,28.0]],config=dict(CFG,Wait=False,Timeout=2,Delay=0))
effects(before,['CMD2']);equal(acquisition_waits(),[False])
""")
add('send-delay:failure', """
before=mark()
assert not Send(command='CMD1',verify=[['TM.POWER.BUS_VOLTAGE',eq,0,{Retries:0}]],config=dict(CFG,Wait=False,Timeout=2,Delay=.75,OnFalse=NOACTION))
effects(before,['CMD1']);equal(acquisition_waits(),[False])
""")
add('send-delay:recovery', """
before=mark()
assert Send(command='CMD2',verify=[['TM.POWER.BUS_VOLTAGE',eq,28.0]],config=dict(CFG,Wait=False,Timeout=2,Delay=TIME(.5)))
effects(before,['CMD2']);equal(acquisition_waits(),[False])
""")
add('waitfor-delay:positive', """
expected=fresh_setup();before=mark()
assert WaitFor(['TM.CORE.TICK',eq,expected],Wait=True,Timeout=2,Delay=3,PromptUser=False,HandleError=False)
effects(before,[]);fresh_assert(expected)
""")
add('waitfor-delay:boundary', """
fixture('feed',value=False);fixture('tick');before=mark()
assert WaitFor(['TM.POWER.BUS_VOLTAGE',eq,28.0],Wait=False,Timeout=.3,Delay=0,PromptUser=False,HandleError=False)
effects(before,[]);equal(acquisition_waits(),[False])
""")
add('internal-policy:positive', """
before=mark()
assert WaitFor(['TM.POWER.BUS_VOLTAGE',eq,28.0],Wait=False,Timeout=2,Delay=3,PromptUser=False,HandleError=False)
effects(before,[])
equal(set(acquisition_configs()[0]),{Wait,Timeout,ValueFormat})
""")
add('internal-policy:boundary', """
before=mark()
equal(GetTM('TM.POWER.BUS_VOLTAGE',Wait=False,Timeout=2,InWaitFor=False,HandleError=False),28.0)
effects(before,[]);equal(set(acquisition_configs()[0]),{Wait,Timeout,ValueFormat})
""")
add('internal-policy:failure', """
before=mark()
for key,value in [('InWaitFor','yes'),('Confirm',False),('ConfirmCritical',False),('Time',0),('SendDelay',0),('Sequence',False),('Block',False),('ReleaseTime',0)]:
    rejects(DriverException,lambda:GetTM('TM.POWER.BUS_VOLTAGE',config={Wait:False,Timeout:2,HandleError:False,key:value}))
effects(before,[]);equal(acquisitions(),[])
""")
add('internal-policy:recovery', """
before=mark()
equal(GetTM('TM.POWER.BUS_VOLTAGE',Wait=False,Timeout=2,HandleError=False),28.0)
effects(before,[]);equal(acquisition_waits(),[False])
""")

add('gettm-wait:positive', "expected=fresh_setup();before=mark()\nequal(GetTM('TM.CORE.TICK',Wait=True,Timeout=2,HandleError=False),expected)\neffects(before,[]);fresh_assert(expected)")

add('gettm-wait:recovery', "expected=fresh_setup();before=mark()\nequal(GetTM('TM.CORE.TICK',Wait=True,Timeout=2,HandleError=False),expected)\neffects(before,[]);fresh_assert(expected)")

add('gettm-wait:boundary', "fixture('feed',value=False);tick=fixture('tick')['state']['core']['tick'];before=mark()\nequal(GetTM('TM.CORE.TICK',Wait=False,Timeout=.3,HandleError=False),tick)\neffects(before,[]);equal(acquisition_waits(),[False])")

add('gettm-wait:failure', "fixture('feed',value=False);fixture('tick');before=mark()\nrejects(DriverException,lambda:GetTM('TM.POWER.BUS_VOLTAGE',Wait=True,Timeout=.3,HandleError=False))\neffects(before,[]);equal(acquisition_waits(),[True]);equal(len(acquisitions()),1);assert 'error' in acquisitions()[0]")

add('verify-wait:positive', "expected=fresh_setup();before=mark()\nassert Verify('TM.CORE.TICK',eq,expected,Wait=True,Timeout=2,HandleError=False,PromptUser=False,OnFalse=NOACTION,Retries=0)\neffects(before,[]);fresh_assert(expected)")

add('verify-wait:recovery', "expected=fresh_setup();before=mark()\nassert Verify('TM.CORE.TICK',eq,expected,Wait=True,Timeout=2,HandleError=False,PromptUser=False,OnFalse=NOACTION,Retries=0)\neffects(before,[]);fresh_assert(expected)")

add('verify-wait:boundary', "fixture('feed',value=False);tick=fixture('tick')['state']['core']['tick'];before=mark()\nassert Verify('TM.CORE.TICK',eq,tick,Wait=False,Timeout=.3,HandleError=False,PromptUser=False,OnFalse=NOACTION,Retries=0)\neffects(before,[]);equal(acquisition_waits(),[False])")

add('verify-wait:failure', "fixture('feed',value=False);fixture('tick');before=mark()\nrejects(DriverException,lambda:Verify('TM.POWER.BUS_VOLTAGE',eq,28.0,Wait=True,Timeout=.3,HandleError=False,PromptUser=False,OnFalse=NOACTION,Retries=0))\neffects(before,[]);equal(acquisition_waits(),[True]);equal(len(acquisitions()),1);assert 'error' in acquisitions()[0]")

add('condition-strictness:failure', """
before=mark()
rejects(DriverException,lambda:Send(command='CMD1',verify=[['TM.POWER.BUS_VOLTAGE',eq,28.0,{Time:0}]],config=dict(CFG,Wait=False,Timeout=2)))
effects(before,['CMD1']);equal(acquisitions(),[])
""")
add('condition-strictness:recovery', """
before=mark()
assert Send(command='CMD2',verify=[['TM.POWER.BUS_VOLTAGE',eq,28.0,{Wait:False}]],config=dict(CFG,Wait=True,Timeout=2))
effects(before,['CMD2']);equal(acquisition_waits(),[False])
""")
add('wait-type:failure', """
before=mark()
rejects(DriverException,lambda:WaitFor(['TM.POWER.BUS_VOLTAGE',eq,28.0],Wait='yes',Timeout=2,Delay=3,PromptUser=False,HandleError=False))
effects(before,[]);equal(len(acquisitions()),1);assert 'error' in acquisitions()[0]
""")
add('wait-type:recovery', """
before=mark()
assert WaitFor(['TM.POWER.BUS_VOLTAGE',eq,28.0],Wait=False,Timeout=2,Delay=3,PromptUser=False,HandleError=False)
effects(before,[]);equal(acquisition_waits(),[False])
""")

# Run recovery after the corresponding known acquisition failure.
for family in ('gettm', 'verify'):
    reordered = {family+'-wait:'+dimension: CASES.pop(family+'-wait:'+dimension)
                 for dimension in ('positive', 'boundary', 'failure', 'recovery')}
    CASES.update(reordered)

# Wait alone is eligible; Delay/Timeout and full composed functions stay open.
for key in CASES:
    if key.split(':')[0] in ('gettm-wait','verify-wait','send-wait','waitfor-wait'):
        METADATA[key]['contracts']=['CMP-LRM244-MODIFIER-WAIT']
        METADATA[key]['oracle']='Original native operation with actual DSS STEP publication, exact protobuf sample and immutable TC receipts; fresh/recorded value, failure, recovery separately asserted.'
