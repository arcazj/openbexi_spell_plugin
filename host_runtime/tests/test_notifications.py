"""Native procedure-table data preserves wire values, location and ordering."""
from datetime import datetime
from pathlib import Path
import queue
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from adapter import Adapter


class Peer:
    instance = 'main#1'

    def __init__(self):
        self.events = queue.Queue()
        self.closed = False

    def request(self, command):
        return {'ExecutorStatus': 'FINISHED'}

    def close(self):
        self.closed = True


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.adapter = Adapter()
        self.peer = Peer()
        self.adapter.session = self.peer
        self.adapter.host_root = 'C:/project'
        self.messages = []
        self.adapter.emit = self.messages.append

    def publish(self, identifier, **fields):
        self.peer.events.put({'message': {'id': identifier, 'fields': fields}})

    def test_native_item_fields_and_innermost_location_are_preserved(self):
        fields = dict(ProcId='main#1', DataType='ITEM', Csp='main:3:sub/telemetry:12/4',
                      Time='2026-10-17 19:41:00', Sequence='7', ItemType='VERIFICATION',
                      ItemName='TEMP\4PRESSURE', ItemValue='20\x0430', ItemStatus='SUCCESS',
                      ItemReason='Within range', ItemTime='native item timestamp', SCount='2')
        original = dict(fields)
        self.publish('MSG_NOTIFICATION', **fields)
        self.adapter.drain_events()
        self.assertEqual(len(self.messages), 1)
        message = self.messages[0]
        self.assertEqual(message['event'], 'spell/notification')
        self.assertEqual({key: message['body'][key] for key in fields}, original)
        self.assertEqual(message['body']['source'],
                         {'name': 'telemetry.py', 'path': 'C:/project/sub/telemetry.py'})
        self.assertEqual(message['body']['line'], 12)
        self.assertEqual(message['body']['rootProcedureId'], 'main#1')
        self.assertIsNotNone(datetime.fromisoformat(message['body']['receivedAt']).tzinfo)
        self.assertEqual(fields, original)

    def test_status_is_scoped_to_its_procedure_and_does_not_change_root_state(self):
        self.adapter.await_running = True
        self.publish('MSG_NOTIFICATION', ProcId='child#0', DataType='STATUS', ExecutorStatus='RUNNING')
        self.publish('MSG_ERROR', ProcId='child#0', DataType='STATUS', ExecutorStatus='ERROR',
                     ErrorMsg='Child failure', ErrorReason='Native reason')
        self.adapter.drain_events()
        self.assertEqual([message['event'] for message in self.messages], ['spell/status', 'spell/status'])
        self.assertEqual(self.messages[1]['body']['ErrorReason'], 'Native reason')
        self.assertEqual(self.messages[1]['body']['rootProcedureId'], 'main#1')
        self.assertTrue(self.adapter.await_running)
        self.assertIsNone(self.adapter.notified_status)
        self.assertEqual(self.adapter.status_revision, 0)

    def test_item_and_terminal_status_are_delivered_before_exit(self):
        self.adapter.configured = True
        self.publish('MSG_NOTIFICATION', ProcId='main#1', DataType='CURRENT_LINE', Csp='main:2/0')
        self.publish('MSG_NOTIFICATION', ProcId='main#1', DataType='ITEM', ItemStatus='SUCCESS')
        self.publish('MSG_WRITE', ProcId='main#1', Text='Native output')
        self.publish('MSG_NOTIFICATION', ProcId='main#1', DataType='STATUS', ExecutorStatus='FINISHED')
        self.adapter.poll()
        self.assertEqual([message['event'] for message in self.messages],
                         ['spell/notification', 'spell/notification', 'output', 'spell/status',
                          'exited', 'terminated'])
        self.assertTrue(self.peer.closed)

    def test_unresolvable_and_external_locations_retain_data_without_navigation(self):
        for csp in ('', 'main', 'main:0/0', '../external:4/0', '/lib/external:4/0',
                    'C:/external:4/0', 'main:2:../outside:5/0', 'main:4/bad'):
            with self.subTest(csp=csp):
                body = self.adapter.notification_body({'Csp': csp})
                self.assertEqual(body['Csp'], csp)
                self.assertNotIn('source', body)
                self.assertNotIn('line', body)

    def test_plain_stack_position_and_subdirectory_source(self):
        body = self.adapter.notification_body({'Csp': 'folder/main:5'})
        self.assertEqual(body['source']['path'], 'C:/project/folder/main.py')
        self.assertEqual(body['line'], 5)


if __name__ == '__main__':
    unittest.main()
