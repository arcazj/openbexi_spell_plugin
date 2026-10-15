"""Startup retries must be bounded and must never replay native requests."""
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from native import Bridge, BridgeConnectionError, NativeSession


class NativeStartupTests(unittest.TestCase):
    def session(self):
        session = object.__new__(NativeSession)
        session.process = Mock()
        session.process.poll.return_value = None
        session.log = Mock()
        session.events = queue.Queue()
        return session

    def test_delayed_context_accepts_before_deadline(self):
        session = self.session()
        connected = Mock()
        with patch('native.Bridge', side_effect=[BridgeConnectionError('refused'), connected]) as bridge, \
                patch('native.time.monotonic', side_effect=[1, 1.1, 1.2]), \
                patch('native.time.sleep'):
            self.assertIs(session.connect_bridge(123, {}, 2), connected)
        self.assertEqual(bridge.call_count, 2)
        self.assertAlmostEqual(bridge.call_args.kwargs['connect_timeout'], .8)
        connected.exchange.assert_not_called()

    def test_deadline_retains_original_connection_failure(self):
        session = self.session()
        with patch('native.Bridge', side_effect=BridgeConnectionError('refused')) as bridge, \
                patch('native.time.monotonic', side_effect=[1, 2]):
            with self.assertRaisesRegex(BridgeConnectionError, 'refused'):
                session.connect_bridge(123, {}, 2)
        self.assertEqual(bridge.call_count, 1)

    def test_expired_deadline_does_not_launch_bridge(self):
        with patch('native.Bridge') as bridge, patch('native.time.monotonic', return_value=2):
            with self.assertRaisesRegex(BridgeConnectionError, 'deadline expired'):
                self.session().connect_bridge(123, {}, 2)
        bridge.assert_not_called()

    def test_listener_death_stops_retries(self):
        session = self.session()
        session.process.poll.return_value = 1
        with patch('native.Bridge') as bridge:
            with self.assertRaisesRegex(RuntimeError, 'listener exited'):
                session.connect_bridge(123, {}, 2)
        bridge.assert_not_called()

    def test_non_connection_error_is_not_retried(self):
        with patch('native.Bridge', side_effect=ValueError('invalid port')) as bridge, \
                patch('native.time.monotonic', return_value=1):
            with self.assertRaisesRegex(ValueError, 'invalid port'):
                self.session().connect_bridge(123, {}, 2)
        self.assertEqual(bridge.call_count, 1)

    def test_failed_real_pipe_peer_is_reaped_before_retry(self):
        create = subprocess.Popen
        processes = []
        def launch(*args, **kwargs):
            kwargs.pop('env', None)
            process = create([sys.executable, '-I', '-c', 'raise SystemExit(1)'], **kwargs)
            processes.append(process)
            return process
        with tempfile.TemporaryFile() as log, patch('native.subprocess.Popen', side_effect=launch):
            with self.assertRaises(BridgeConnectionError):
                Bridge(0, {}, log, queue.Queue())
        self.assertEqual(processes[0].returncode, 1)
        self.assertTrue(processes[0].stdin.closed)
        self.assertTrue(processes[0].stdout.closed)
