"""Subprocess bridge-wire support; never claims full native SPELL execution."""

from contextlib import contextmanager
import importlib.util
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[2] / "host_runtime/python/native.py"
spec = importlib.util.spec_from_file_location("bridge_lifecycle_native", PATH)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)

NORMAL = """
for line in sys.stdin:
    request = json.loads(line)
    print(json.dumps({'seq': request['seq'], 'ok': True,
                      'message': {'fields': {'value': '42'}}}), flush=True)
"""


@contextmanager
def peer(
    script=NORMAL,
    *,
    preamble="print(json.dumps({'event':'connected'}), flush=True)",
    bridge_class=None,
    events=None,
):
    original = subprocess.Popen
    children = []

    def launch(*args, **kwargs):
        kwargs.pop("env", None)
        child = original(
            [
                sys.executable,
                "-I",
                "-u",
                "-c",
                "import json,sys,time,os\n" + preamble + "\n" + script,
            ],
            **kwargs,
        )
        children.append(child)
        return child

    events = events if events is not None else queue.Queue(maxsize=256)
    with tempfile.TemporaryFile() as log, patch.object(native.subprocess, "Popen", launch):
        bridge = None
        try:
            bridge = (bridge_class or native.Bridge)(0, {}, log, events)
            yield bridge, events
        finally:
            if bridge is not None:
                bridge.close()
                assert not bridge.thread.is_alive()
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=3)
                for pipe in (child.stdin, child.stdout):
                    if pipe is not None and not pipe.closed:
                        pipe.close()
