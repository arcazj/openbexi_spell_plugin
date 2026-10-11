"""A real pipe peer proves notification pressure cannot hide a synchronous reply."""
import io
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from native import Bridge


class BridgePressureTests(unittest.TestCase):
    def test_reply_behind_more_notifications_than_queue_capacity(self):
        peer = """import json,sys
print(json.dumps({'event':'connected'}), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    for index in range(900):
        print(json.dumps({'event':'notification','index':index}), flush=True)
    print(json.dumps({'seq':request['seq'],'ok':True,'message':{'fields':{'value':'42'}}}), flush=True)
"""
        create = subprocess.Popen
        def launch(*args, **kwargs):
            kwargs.pop('env', None)
            return create([sys.executable, '-I', '-u', '-c', peer], **kwargs)
        events = queue.Queue(maxsize=256)
        with tempfile.TemporaryFile() as log, patch('native.subprocess.Popen', side_effect=launch):
            bridge = Bridge(0, {}, log, events)
            observed = []
            def pump():
                for _ in range(128):
                    try:
                        observed.append(events.get_nowait()['index'])
                    except queue.Empty:
                        return
            try:
                self.assertEqual(bridge.exchange('TEST', 'PEER', pump=pump), {'value': '42'})
                while not events.empty():
                    pump()
                self.assertEqual(observed, list(range(900)))
                self.assertLessEqual(events.qsize(), 256)
            finally:
                bridge.close()
            self.assertFalse(bridge.thread.is_alive())


if __name__ == '__main__':
    unittest.main()
