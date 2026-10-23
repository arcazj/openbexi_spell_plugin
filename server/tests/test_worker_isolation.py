"""Real process memory isolation; native agents must not rely on Yama defaults."""

import json
from pathlib import Path
import subprocess
import sys


def test_agent_disables_dumpability_before_procedure_launch_in_a_real_process():
    script = """import ctypes,json,sys
sys.path.insert(0,ROOT)
from openbexi_spell_server.worker import protect_runtime
control=ctypes.CDLL(None).prctl
before=control(3,0,0,0,0)
protect_runtime()
assert control(3,0,0,0,0)==0
protect_runtime()
assert control(3,0,0,0,0)==0
print(json.dumps(dict(original_dumpable=before,protected=True)))
"""
    root = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-I", "-c", "ROOT=" + repr(root) + "\n" + script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["protected"] is True


def test_same_uid_parent_reads_positive_control_but_cannot_read_protected_winner_memory():
    # A parent is a stronger reader than the native procedure descendant. The
    # positive read proves that denial after protection is not a fake success
    # caused by an unavailable syscall, a wrong PID/address, or Yama alone.
    child = """import ctypes,json,os,sys
sys.path.insert(0,ROOT)
from openbexi_spell_server.worker import protect_runtime
value=ctypes.create_string_buffer(b'qualification-only-memory-proof')
print(json.dumps([os.getpid(),ctypes.addressof(value)]),flush=True)
assert sys.stdin.readline().strip()=='protect'
protect_runtime()
print('protected',flush=True)
sys.stdin.readline()
"""
    controller = """import ctypes,errno,json,subprocess,sys
class IOV(ctypes.Structure):
    _fields_=[('base',ctypes.c_void_p),('length',ctypes.c_size_t)]
libc=ctypes.CDLL(None,use_errno=True)
read=libc.process_vm_readv
read.argtypes=[ctypes.c_int,ctypes.POINTER(IOV),ctypes.c_ulong,ctypes.POINTER(IOV),ctypes.c_ulong,ctypes.c_ulong]
read.restype=ctypes.c_ssize_t
expected=b'qualification-only-memory-proof'
buffer=ctypes.create_string_buffer(len(expected))
local=IOV(ctypes.addressof(buffer),len(expected))
process=subprocess.Popen([sys.executable,'-I','-c',CHILD],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
try:
    pid,address=json.loads(process.stdout.readline())
    remote=IOV(address,len(expected))
    assert read(pid,ctypes.byref(local),1,ctypes.byref(remote),1,0)==len(expected),'Positive control memory read is unavailable'
    assert buffer.raw==expected
    process.stdin.write('protect\\n');process.stdin.flush()
    assert process.stdout.readline().strip()=='protected'
    ctypes.set_errno(0)
    assert read(pid,ctypes.byref(local),1,ctypes.byref(remote),1,0)==-1
    assert ctypes.get_errno() in (errno.EPERM,errno.EACCES)
    process.stdin.write('exit\\n');process.stdin.flush()
    assert process.wait(timeout=3)==0
    print(json.dumps(dict(positive_control_read=True,protected_memory_read_denied=True)))
finally:
    if process.poll() is None:
        process.kill();process.wait()
    process.stdin.close();process.stdout.close()
"""
    root = str(Path(__file__).resolve().parents[1] / "src")
    child = "ROOT=" + repr(root) + "\n" + child
    result = subprocess.run(
        [sys.executable, "-I", "-c", "CHILD=" + repr(child) + "\n" + controller],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == dict(
        positive_control_read=True, protected_memory_read_denied=True
    )
