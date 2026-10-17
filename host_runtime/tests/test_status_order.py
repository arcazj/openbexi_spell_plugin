"""Status-query replies can race newer notifications on the native connection."""
from pathlib import Path
import queue
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from adapter import Adapter


class StatusOrderTests(unittest.TestCase):
    def test_native_error_heading_and_reason_precede_exit_without_duplicate_lines(self):
        for heading, reason, expected in (
                ('Value error\n - file example.py, line 4', 'intentional failure',
                 'Value error\n - file example.py, line 4\nintentional failure\n'),
                ('', 'reason only', 'reason only\n'),
                ('heading only', '', 'heading only\n'),
                ('same', 'same', 'same\n'),
                ('heading\nreason', 'reason', 'heading\nreason\n'),
                ('Context error', 'text', 'Context error\ntext\n'),
                ('heading\nline one\nline two', 'line one\nline two',
                 'heading\nline one\nline two\n')):
            with self.subTest(heading=heading, reason=reason):
                adapter = Adapter()
                messages = []
                adapter.emit = messages.append
                adapter.configured = True
                adapter.notified_status = 'ERROR'
                class Peer:
                    instance = 'main#1'
                    events = queue.Queue()
                    closed = False
                    def request(self, command):
                        return {'ExecutorStatus':'ERROR', 'ErrorMsg':heading, 'ErrorReason':reason}
                    def close(self):
                        self.closed = True
                peer = Peer()
                adapter.session = peer
                adapter.poll()
                self.assertEqual([item['event'] for item in messages], ['output','exited','terminated'])
                self.assertEqual(messages[0]['body'], {'category':'stderr','output':expected})
                self.assertTrue(peer.closed)
                self.assertIsNone(adapter.session)

    def test_stale_pause_reply_after_run_notification_does_not_stop_host(self):
        adapter = Adapter()
        messages = []
        adapter.emit = messages.append
        adapter.configured = True
        adapter.await_running = True
        class Peer:
            instance = 'main#1'
            events = queue.Queue()
            def request(self, command):
                self.events.put({'message': {'fields': {'ProcId':'main#1', 'DataType': 'STATUS', 'ExecutorStatus': 'RUNNING'}}})
                adapter.drain_events()
                return {'ExecutorStatus': 'PAUSED'}
        adapter.session = Peer()
        adapter.poll()
        self.assertEqual([message['event'] for message in messages], ['spell/status'])
        self.assertEqual(messages[0]['body']['ExecutorStatus'], 'RUNNING')
        self.assertFalse(adapter.await_running)
        adapter.session.request = lambda command: {'ExecutorStatus': 'RUNNING'}
        adapter.poll()
        self.assertEqual([message['event'] for message in messages], ['spell/status'])
        adapter.session.events.put({'message': {'fields': {'ProcId':'main#1', 'DataType': 'STATUS', 'ExecutorStatus': 'PAUSED'}}})
        adapter.session.request = lambda command: {'ExecutorStatus': 'PAUSED'}
        adapter.poll()
        self.assertEqual([message['event'] for message in messages], ['spell/status', 'spell/status', 'stopped'])
        self.assertEqual(messages[1]['body']['ExecutorStatus'], 'PAUSED')


if __name__ == '__main__':
    unittest.main()
