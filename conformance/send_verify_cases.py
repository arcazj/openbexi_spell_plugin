"""Actual composed Send checks, without claiming complete inventory families."""
CASES = {}
METADATA = {}


def add(name, code):
    CASES[name] = code
    METADATA[name] = dict(contracts=[], dimension=name.rsplit(':', 1)[-1],
        oracle='Original native Send and verifier; exact independent TM acquisitions and one five-stage TC receipt chain, no implicit resend.')


add('retries:positive', """
before=mark()
assert not Send(command='CMD1',verify=[['TM.POWER.BUS_VOLTAGE',eq,-999]],config=dict(CFG,Wait=False,Timeout=2,Retries=2,OnFalse=NOACTION))
effects(before,['CMD1']);equal(len(acquisitions()),3)
""")
add('retries:boundary', """
before=mark()
assert not Send(command='CMD2',verify=[['TM.POWER.BUS_VOLTAGE',eq,-999]],config=dict(CFG,Wait=False,Timeout=2,Retries=0,OnFalse=NOACTION))
effects(before,['CMD2']);equal(len(acquisitions()),1)
""")
add('retries:failure', """
before=mark()
rejects(DriverException,lambda:Send(command='CMD1',verify=[['TM.POWER.BUS_VOLTAGE',eq,28]],config=dict(CFG,Wait=False,Timeout=2,Retries=-1)))
effects(before,['CMD1']);equal(acquisitions(),[])
""")
add('retries:recovery', """
before=mark()
assert Send(command='CMD2',verify=[['TM.POWER.BUS_VOLTAGE',eq,28]],config=dict(CFG,Wait=False,Timeout=2,Retries=1))
effects(before,['CMD2']);equal(len(acquisitions()),1)
""")
add('retries-override:boundary', """
import copy
before=mark();config=dict(CFG,Wait=False,Timeout=2,Retries=3,OnFalse=NOACTION)
condition=['TM.POWER.BUS_VOLTAGE',eq,-999,{Retries:0}]
original=copy.deepcopy((config,condition))
assert not Send(command='CMD1',verify=[condition],config=config)
effects(before,['CMD1']);equal(len(acquisitions()),1);equal((config,condition),original)
""")

add('ignorecase:positive', """
before=mark()
assert Send(command='CMD1',verify=[['TM.CORE.MODE',eq,'nominal']],config=dict(CFG,Wait=False,Timeout=2,IgnoreCase=True))
effects(before,['CMD1']);equal(len(acquisitions()),1)
""")
add('ignorecase:boundary', """
before=mark()
assert not Send(command='CMD2',verify=[['TM.CORE.MODE',eq,'nominal',{Retries:0}]],config=dict(CFG,Wait=False,Timeout=2,IgnoreCase=False,OnFalse=NOACTION))
effects(before,['CMD2']);equal(len(acquisitions()),1)
""")
add('ignorecase:failure', """
before=mark()
assert not Send(command='CMD1',verify=[['TM.CORE.MODE',eq,'different',{Retries:0}]],config=dict(CFG,Wait=False,Timeout=2,IgnoreCase=True,OnFalse=NOACTION))
effects(before,['CMD1']);equal(len(acquisitions()),1)
""")
add('ignorecase:recovery', """
before=mark()
assert Send(command='CMD2',verify=[['TM.CORE.MODE',eq,'NOMINAL']],config=dict(CFG,Wait=False,Timeout=2,IgnoreCase=False))
effects(before,['CMD2']);equal(len(acquisitions()),1)
""")
add('ignorecase-override:boundary', """
before=mark()
assert not Send(command='CMD1',verify=[['TM.CORE.MODE',eq,'nominal',{IgnoreCase:False,Retries:0}]],config=dict(CFG,Wait=False,Timeout=2,IgnoreCase=True,OnFalse=NOACTION))
effects(before,['CMD1']);equal(len(acquisitions()),1)
""")

add('valueformat:positive', """
before=mark()
assert Send(command='CMD1',verify=[['TM.POWER.BUS_VOLTAGE',eq,28000]],config=dict(CFG,Wait=False,Timeout=2,ValueFormat=RAW))
effects(before,['CMD1']);equal(acquisition_configs()[0][ValueFormat],RAW)
""")
add('valueformat:boundary', """
before=mark()
assert Send(command='CMD2',verify=[['TM.POWER.BUS_VOLTAGE',eq,28]],config=dict(CFG,Wait=False,Timeout=2,ValueFormat=ENG))
effects(before,['CMD2']);equal(acquisition_configs()[0][ValueFormat],ENG)
""")
add('valueformat:failure', """
before=mark()
assert not Send(command='CMD1',verify=[['TM.POWER.BUS_VOLTAGE',eq,28,{Retries:0}]],config=dict(CFG,Wait=False,Timeout=2,ValueFormat=RAW,OnFalse=NOACTION))
effects(before,['CMD1']);equal(acquisition_configs()[0][ValueFormat],RAW)
""")
add('valueformat:recovery', """
before=mark()
assert Send(command='CMD2',verify=[['TM.POWER.BUS_VOLTAGE',eq,28000]],config=dict(CFG,Wait=False,Timeout=2,ValueFormat=RAW))
effects(before,['CMD2']);equal(acquisition_configs()[0][ValueFormat],RAW)
""")
add('valueformat-override:boundary', """
import copy
before=mark();config=dict(CFG,Wait=False,Timeout=2,ValueFormat=RAW)
conditions=[['TM.POWER.BUS_VOLTAGE',eq,28,{ValueFormat:ENG}],['TM.POWER.BUS_VOLTAGE',eq,28000]]
original=copy.deepcopy((config,conditions))
assert Send(command='CMD1',verify=conditions,config=config)
effects(before,['CMD1']);equal(sorted(c[ValueFormat] for c in acquisition_configs()),sorted([ENG,RAW]))
equal((config,conditions),original)
""")

add('direct-tc:failure', """
before=mark()
for options in ({Retries:0},{IgnoreCase:True},{ValueFormat:RAW}):
    rejects(DriverException,lambda:Send(command='CMD1',config=dict(CFG,**options)))
effects(before,[]);equal(acquisitions(),[])
""")
add('direct-tc:recovery', """
before=mark()
assert Send(command='CMD2',config=CFG)
effects(before,['CMD2']);equal(acquisitions(),[])
""")
add('composed:positive', """
before=mark()
assert Send(command='CMD1',verify=[['TM.POWER.BUS_VOLTAGE',eq,28000],['TM.CORE.MODE',eq,'nominal']],config=dict(CFG,Wait=False,Timeout=2,Retries=0,IgnoreCase=True,ValueFormat=RAW))
effects(before,['CMD1']);equal(len(acquisitions()),2)
""")
