"""Failure fixtures for the original context-owned service watchdog.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from pathlib import Path


def write_service(directory: Path, scenario: str):
    assert scenario in ('failure', 'crash')
    prefix = '/out/service-' + scenario
    code = r"""##########
# NAME: Native service restart qualification
# SPACECRAFT: Y
# PYTHON VERSION: 3
##########
from spell.utils.spell_service import SpellService

@SpellService(name='native_resilient')
class NativeResilient:
    def __init__(self,name): self.name=name
    def startService(self):
        import os,time
        from pathlib import Path
        from spell.runtime import ARGS,IVARS,PROC
        assert len(ARGS)==0 and PROC['NAME']=='native_resilient'
        prefix=PREFIX
        pid=os.getpid()
        starts=Path(prefix+'-starts.txt')
        generation=len(starts.read_text().splitlines())+1 if starts.exists() else 1
        IVARS['answer']=self.execute(lambda:6*7).result(timeout=3)
        assert IVARS['answer']==42
        try:
            with starts.open('a') as record:
                record.write(str(pid)+'\n')
                record.flush()
                os.fsync(record.fileno())
            while True:
                if SCENARIO=='failure' and generation==1 and Path(prefix+'-trigger.txt').exists():
                    raise ValueError('intentional service failure')
                time.sleep(0.02)
        finally:
            with open(prefix+'-closed.txt','a') as record: record.write(str(pid)+'\n')
    def isAlive(self): return False
"""
    code = code.replace('PREFIX', repr(prefix)).replace('SCENARIO', repr(scenario))
    compile(code, 'native_resilient.py', 'exec')
    (directory / 'native_resilient.py').write_text(code, encoding='utf-8')
