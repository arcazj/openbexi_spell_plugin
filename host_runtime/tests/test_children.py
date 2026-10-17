"""Child startup must preserve native manual mode and parent status ordering."""
from pathlib import Path
import queue
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from adapter import Adapter
from children import ChildProcedures
from native import NativeSession


def operation(procedure='child#0', parent='main#1', operation='OPEN'):
    return {'id': 'MSG_EXEC_OP', 'fields': {
        'ProcId': procedure, 'ParentId': parent, 'ExecOp': operation}}


class Peer:
    instance = 'main#1'

    def __init__(self):
        self.events = queue.Queue()
        self.calls = []
        self.status = 'PAUSED'
        self.mode = '{Automatic:True,Visible:True,Blocking:True}'

    def request(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return {'ExecutorStatus': self.status, 'OpenMode': self.mode}


class ChildTests(unittest.TestCase):
    def test_source_presentation_obeys_visibility_and_open_lifetime(self):
        shown=[]
        children=ChildProcedures('main#1',shown.append);peer=Peer()
        children.observe(operation('unrelated#0','other#1'))
        children.observe(operation());children.service(peer);children.service(peer)
        self.assertEqual(shown,['child#0'])
        children.observe(operation(operation='CLOSE'))
        children.observe(operation());children.service(peer)
        self.assertEqual(shown,['child#0','child#0'])
        for visible in ('False','True'):
            peer.mode='{Automatic:False,Visible:'+visible+',Blocking:False}'
            children.observe(operation('manual-'+visible+'#0'));children.service(peer)
        self.assertEqual(shown,['child#0','child#0','manual-True#0'])

    def test_source_console_keeps_exact_content_and_rejects_project_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            project=Path(directory);(project/'Bus').mkdir()
            source='# Child source\n'+"value='é'\n"*3000
            (project/'Bus/child.py').write_text(source,encoding='utf-8',newline='\n')
            adapter=Adapter();adapter.session=type('Session',(),dict(project=project, instance='main#0'))()
            adapter.host_root='C:/client/project';messages=[]
            adapter.emit=messages.append
            adapter.present_child('Bus/child#0')
            outputs=[m['body'] for m in messages if m.get('event') == 'output']
            snapshots=[m['body'] for m in messages if m.get('event') == 'spell/source']
            self.assertEqual(''.join(row['text'] for row in snapshots), source)
            self.assertEqual(snapshots[0]['offset'], 0)
            self.assertTrue(snapshots[-1]['complete'])
            self.assertTrue(all(row['procedureId'] == 'Bus/child#0' and row['rootProcedureId'] == 'main#0' for row in snapshots))
            self.assertEqual(''.join(row['output'] for row in outputs[1:-1]),source)
            self.assertTrue(all(row['category']=='console' for row in outputs))
            self.assertTrue(all(row['source']['path']=='C:/client/project/Bus/child.py' for row in outputs))
            self.assertTrue(all(len(row['output'])<=16384 for row in outputs))
            with self.assertRaisesRegex(ValueError,'outside'):adapter.present_child('../escape#0')
            adapter.present_child('missing#0')
            self.assertEqual(messages[-1]['body']['category'],'stderr')

    def test_only_owned_children_and_grandchildren_start_once_after_loading(self):
        children = ChildProcedures('main#1')
        peer = Peer()
        children.observe(operation('unrelated#0', 'other#1'))
        children.observe(operation('main#1', 'main#1'))
        children.observe(operation())
        children.observe(operation('grandchild#0', 'child#0'))
        self.assertEqual(peer.calls, [])  # observation never issues reentrant IPC
        peer.status = 'LOADED'
        children.service(peer)
        self.assertTrue(all(command == 'REQ_EXEC_INFO' for command, _ in peer.calls))
        peer.status = 'PAUSED'
        children.service(peer)
        children.observe(operation())  # duplicate OPEN and later PAUSED do not restart
        children.service(peer)
        self.assertEqual([args['procedure'] for cmd, args in peer.calls if cmd == 'CMD_RUN'],
                         ['child#0', 'grandchild#0'])
        children.observe(operation(operation='CLOSE'))
        children.observe(operation())  # a newly opened instance can reuse an ID
        children.service(peer)
        self.assertEqual(sum(cmd == 'CMD_RUN' for cmd, _ in peer.calls), 3)

    def test_manual_hidden_running_terminal_or_invalid_mode_never_auto_runs(self):
        for mode, status in (
            ('{Automatic:False,Visible:True,Blocking:True}', 'PAUSED'),
            ('{Automatic:True,Visible:False,Blocking:True}', 'PAUSED'),
            ('{Automatic:True,Visible:True,Blocking:False}', 'RUNNING'),
            ('{Automatic:True,Visible:True,Blocking:True}', 'ERROR'),
            ('{Automatic:True,Visible:True,Blocking:True}', 'FINISHED'),
        ):
            with self.subTest(mode=mode, status=status):
                children, peer = ChildProcedures('main#1'), Peer()
                peer.mode, peer.status = mode, status
                children.observe(operation())
                children.service(peer)
                peer.status = 'PAUSED'
                children.service(peer)
                self.assertEqual([command for command, _ in peer.calls], ['REQ_EXEC_INFO'])
        children, peer = ChildProcedures('main#1'), Peer()
        peer.mode = '{Automatic:arbitrary_code(),Visible:True,Blocking:True}'
        children.observe(operation())
        with self.assertRaisesRegex(RuntimeError, 'Invalid native child open mode'):
            children.service(peer)
        self.assertEqual([command for command, _ in peer.calls], ['REQ_EXEC_INFO'])

    def test_close_notification_during_info_reply_does_not_run_closed_child(self):
        children, peer = ChildProcedures('main#1'), Peer()
        children.observe(operation())
        original = peer.request
        def reply(command, **kwargs):
            children.observe(operation(operation='CLOSE'))
            return original(command, **kwargs)
        peer.request = reply
        children.service(peer)
        self.assertEqual([command for command, _ in peer.calls], ['REQ_EXEC_INFO'])

    def test_uncertain_run_send_is_not_replayed(self):
        children, peer = ChildProcedures('main#1'), Peer()
        children.observe(operation())
        original = peer.request
        def reply(command, **kwargs):
            result = original(command, **kwargs)
            if command == 'CMD_RUN':
                raise RuntimeError('Native reply timed out')
            return result
        peer.request = reply
        with self.assertRaisesRegex(RuntimeError, 'timed out'):
            children.service(peer)
        children.service(peer)
        self.assertEqual(sum(cmd == 'CMD_RUN' for cmd, _ in peer.calls), 1)

    def test_child_status_cannot_release_parent_startup_or_terminal_barrier(self):
        adapter, peer = Adapter(), Peer()
        messages = []
        adapter.emit = messages.append
        adapter.session = peer
        adapter.children = ChildProcedures(peer.instance)
        adapter.await_running = True
        adapter.notified_status = 'WAITING'
        for status in ('RUNNING', 'PAUSED', 'FINISHED', 'ERROR', 'ABORTED'):
            peer.events.put({'message': {'id':'MSG_NOTIFICATION', 'fields': {
                'ProcId':'child#0', 'DataType':'STATUS', 'ExecutorStatus':status}}})
        adapter.drain_events()
        self.assertTrue(adapter.await_running)
        self.assertEqual(adapter.notified_status, 'WAITING')
        self.assertEqual(adapter.status_revision, 0)
        self.assertEqual([message['body']['ExecutorStatus'] for message in messages],
                         ['RUNNING', 'PAUSED', 'FINISHED', 'ERROR', 'ABORTED'])

    def test_native_requests_route_context_and_executor_to_explicit_child(self):
        session = object.__new__(NativeSession)
        session.instance, session.pump = 'main#1', None
        calls = []
        class Context:
            def exchange(self, *args, **kwargs):
                calls.append((args, kwargs))
                return {}
        session.context = Context()
        session.request('REQ_EXEC_INFO', {'ProcId':'wrong'}, context=True, procedure='child#0')
        session.request('CMD_RUN', send=True, procedure='child#0')
        session.request('REQ_EXEC_STATUS')
        self.assertEqual([args[1:] for args, _ in calls], [
            ('CTX', {'ProcId':'child#0'}), ('child#0', {'ProcId':'child#0'}),
            ('main#1', {'ProcId':'main#1'})])


if __name__ == '__main__':
    unittest.main()
