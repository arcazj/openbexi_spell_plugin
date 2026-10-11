"""Owned native processes for context crash/reconnection qualification."""
from pathlib import Path


def write_fixture(directory: Path, service: bool):
    name = 'native_live_service' if service else 'native_live_executor'
    body = f'''import os,time,signal,faulthandler,ctypes,re
with open('/usr/include/linux/prctl.h') as header:
    ptracer=int(re.search(r'#\\s*define\\s+PR_SET_PTRACER\\s+(0x[0-9a-fA-F]+)',header.read()).group(1),16)
native=ctypes.CDLL(None,use_errno=True)
native.prctl.argtypes=[ctypes.c_int]+[ctypes.c_ulong]*4
permission=native.prctl(ptracer,ctypes.c_ulong(-1).value,0,0,0)
with open('/out/{name}-ptracer.txt','w') as record:
    record.write(str((permission,ctypes.get_errno())))
diagnostics=open('/out/{name}-stacks.txt','w')
faulthandler.register(signal.SIGUSR1,file=diagnostics,all_threads=True)
with open('/out/{name}-starts.txt','a') as record:
    record.write(str(os.getpid())+' '+str(os.getppid())+'\\n')
try:
    while True:
        with open('/out/{name}-progress.txt','a') as record: record.write('progress\\n')
        time.sleep(0.04)
finally:
    with open('/out/{name}-closed.txt','w') as record: record.write(str(os.getpid()))
'''
    if service:
        body = """from spell.utils.spell_service import SpellService
@SpellService(name='native_live_service')
class NativeLiveService:
    def __init__(self,name): pass
    def isAlive(self): return False
    def startService(self):
""" + ''.join('        ' + line + '\n' for line in body.splitlines())
    (directory / (name + '.py')).write_text('''##########
# NAME: Native live context reconnect
# SPACECRAFT: Y
# PYTHON VERSION: 3
##########
''' + body)
