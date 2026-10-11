"""Status-query replies can race newer notifications on the native connection."""
from pathlib import Path
import queue
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from adapter import Adapter


class StatusOrderTests(unittest.TestCase):
    def test_stale_pause_reply_after_run_notification_does_not_stop_host(self):
        adapter = Adapter()
        messages = []
        adapter.emit = messages.append
        adapter.configured = True
        adapter.await_running = True
        class Peer:
            events = queue.Queue()
            def request(self, command):
                self.events.put({'message': {'fields': {'DataType': 'STATUS', 'ExecutorStatus': 'RUNNING'}}})
                adapter.drain_events()
                return {'ExecutorStatus': 'PAUSED'}
        adapter.session = Peer()
        adapter.poll()
        self.assertEqual(messages, [])
        self.assertFalse(adapter.await_running)
        adapter.session.request = lambda command: {'ExecutorStatus': 'RUNNING'}
        adapter.poll()
        self.assertEqual(messages, [])
        adapter.session.events.put({'message': {'fields': {'DataType': 'STATUS', 'ExecutorStatus': 'PAUSED'}}})
        adapter.session.request = lambda command: {'ExecutorStatus': 'PAUSED'}
        adapter.poll()
        self.assertEqual([message['event'] for message in messages], ['stopped'])


if __name__ == '__main__':
    unittest.main()
