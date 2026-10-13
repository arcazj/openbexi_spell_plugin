"""Prompt ownership, exposure order and no-effect rejection at the host boundary."""
from pathlib import Path
import queue
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from adapter import Adapter
from children import ChildProcedures
from prompts import PromptQueue


def message(procedure='main#1', text='Choose', sequence='1'):
    return {'id':'MSG_PROMPT', 'fields':{'ProcId':procedure, 'Text':text,
        'ExpectedValues':'yes\4no', 'MsgSequence':sequence}}


class Peer:
    instance = 'main#1'

    def __init__(self):
        self.events = queue.Queue()
        self.calls = []
        self.status = 'PROMPT'
        self.during = None

    def request(self, command, fields=None, **kwargs):
        self.calls.append((command, fields, kwargs))
        if self.during:
            self.during(command)
        return {'ExecutorStatus':self.status}


class PromptTests(unittest.TestCase):
    def setup_adapter(self):
        adapter, peer = Adapter(), Peer()
        adapter.session = peer
        adapter.prompts = PromptQueue(peer.instance)
        adapter.children = ChildProcedures(peer.instance)
        adapter.children.children = {'child#0':{}, 'sibling#0':{}}
        output = []
        adapter.event = lambda event, **body: output.append(('event',event,body))
        adapter.response = lambda request, body=None, error=None: output.append(('response',request['seq'],error))
        return adapter, peer, output

    def publish(self, adapter, peer, *messages):
        for value in messages:
            peer.events.put({'message':value})
        adapter.drain_events()

    def answer(self, adapter, text='yes', **args):
        adapter.answer_prompt({'command':'openbexi/input','seq':10}, dict(text=text,**args))

    def test_root_prompt_preserves_native_fields_and_unscoped_answer(self):
        adapter, peer, output = self.setup_adapter()
        self.publish(adapter,peer,message())
        prompt = next(row[2] for row in output if row[:2]==('event','spell/prompt'))
        self.assertEqual(prompt['ProcId'],'main#1')
        self.assertEqual(prompt['promptId'],'1')
        self.answer(adapter)
        self.assertEqual(peer.calls,[('REQ_EXEC_STATUS',None,{'procedure':'main#1'}),
            ('MSG_ANSWER',{'ReturnValue':'yes'},{'send':True,'procedure':'main#1'})])
        self.assertIsNone(adapter.prompts.active)

    def test_only_active_child_is_exposed_and_next_follows_answer_response(self):
        adapter, peer, output = self.setup_adapter()
        self.publish(adapter,peer,message('child#0','Child'),message('sibling#0','Sibling'))
        self.assertEqual([row[2]['procedureId'] for row in output if row[:2]==('event','openbexi/inputRequest')],['child#0'])
        self.assertFalse(any('Sibling' in str(row) for row in output))
        self.answer(adapter,procedureId='arbitrary#9')  # never accepted as a routing target
        self.assertEqual(peer.calls[-1][2]['procedure'],'child#0')
        response = next(i for i,row in enumerate(output) if row[0]=='response')
        second = next(i for i,row in enumerate(output) if row[:2]==('event','openbexi/inputRequest') and row[2]['procedureId']=='sibling#0')
        self.assertLess(response,second)

    def test_stale_and_duplicate_tokens_have_no_native_effect(self):
        adapter, peer, output = self.setup_adapter()
        self.publish(adapter,peer,message('child#0'),message('sibling#0'))
        self.answer(adapter,promptId='unknown')
        self.assertEqual(peer.calls,[])
        self.assertIsInstance(output[-4][2],ValueError)
        self.answer(adapter,promptId='1')
        before=list(peer.calls)
        self.answer(adapter,promptId='1')
        self.assertEqual(peer.calls,before)
        self.assertEqual(adapter.prompts.active.procedure,'sibling#0')

    def test_foreign_and_duplicate_notifications_are_not_exposed(self):
        adapter, peer, output = self.setup_adapter()
        self.publish(adapter,peer,message('foreign#0'),message('child#0'),message('child#0'))
        self.assertEqual(sum(row[:2]==('event','spell/prompt') for row in output),1)
        self.assertEqual(adapter.prompts.pending,[])

    def test_child_close_during_status_query_prevents_answer(self):
        adapter, peer, output = self.setup_adapter()
        self.publish(adapter,peer,message('child#0'))
        def close(command):
            self.publish(adapter,peer,{'id':'MSG_EXEC_OP','fields':{'ProcId':'child#0','ExecOp':'CLOSE'}})
        peer.during=close
        self.answer(adapter)
        self.assertEqual([call[0] for call in peer.calls],['REQ_EXEC_STATUS'])
        self.assertIsInstance(output[-1][2],ValueError)

    def test_nonprompt_status_rejects_without_answer(self):
        adapter, peer, output = self.setup_adapter()
        self.publish(adapter,peer,message('child#0'))
        peer.status='WAITING'
        self.answer(adapter)
        self.assertEqual([call[0] for call in peer.calls],['REQ_EXEC_STATUS'])
        self.assertIsNone(adapter.prompts.active)

    def test_terminal_and_close_remove_pending_and_exposed_prompts(self):
        adapter, peer, output = self.setup_adapter()
        self.publish(adapter,peer,message('child#0'),message('sibling#0'))
        self.publish(adapter,peer,{'id':'MSG_NOTIFICATION','fields':{
            'ProcId':'sibling#0','DataType':'STATUS','ExecutorStatus':'ABORTED'}})
        self.assertEqual(adapter.prompts.pending,[])
        self.publish(adapter,peer,{'id':'MSG_EXEC_OP','fields':{'ProcId':'child#0','ExecOp':'KILL'}})
        self.assertIsNone(adapter.prompts.active)
        self.answer(adapter)
        self.assertEqual(peer.calls,[])

    def test_uncertain_send_fails_session_without_replay_or_next_exposure(self):
        adapter, peer, output = self.setup_adapter()
        self.publish(adapter,peer,message('child#0'),message('sibling#0'))
        def fail(command):
            if command=='MSG_ANSWER':
                raise RuntimeError('Native reply timed out')
        peer.during=fail
        self.answer(adapter)
        self.assertIsNotNone(adapter.prompts.failure)
        self.answer(adapter)
        self.assertEqual(sum(call[0]=='MSG_ANSWER' for call in peer.calls),1)
        self.assertFalse(any('sibling#0' in str(row) for row in output))
        with self.assertRaisesRegex(RuntimeError,'uncertain'):
            adapter.drain_events()

    def test_successive_prompt_during_send_is_withheld_until_response(self):
        adapter, peer, output = self.setup_adapter()
        self.publish(adapter,peer,message('child#0','First'))
        def next_prompt(command):
            if command=='MSG_ANSWER':
                self.publish(adapter,peer,message('child#0','Second','2'))
                self.assertFalse(any('Second' in str(row) for row in output))
        peer.during=next_prompt
        self.answer(adapter)
        self.assertEqual(adapter.prompts.active.identifier,'2')
        response=next(i for i,row in enumerate(output) if row[0]=='response')
        second=next(i for i,row in enumerate(output) if 'Second' in str(row))
        self.assertLess(response,second)

    def test_status_transport_error_keeps_same_prompt_for_retry(self):
        adapter, peer, output = self.setup_adapter()
        self.publish(adapter,peer,message('child#0'))
        peer.during=lambda command: (_ for _ in ()).throw(RuntimeError('query failed'))
        self.answer(adapter)
        self.assertIsNone(adapter.prompts.failure)
        self.assertEqual(adapter.prompts.active.identifier,'1')
        peer.during=None
        self.answer(adapter,promptId='1')
        self.assertEqual(sum(call[0]=='MSG_ANSWER' for call in peer.calls),1)

    def test_expired_default_prompt_allows_next_prompt_from_same_procedure(self):
        for status in ('RUNNING','WAITING','PAUSED'):
            with self.subTest(status=status):
                adapter,peer,output=self.setup_adapter()
                self.publish(adapter,peer,message('child#0','Expired'))
                self.publish(adapter,peer,{'id':'MSG_NOTIFICATION','fields':{
                    'ProcId':'child#0','DataType':'STATUS','ExecutorStatus':status}},
                    message('child#0','Next','2'))
                self.assertEqual(adapter.prompts.active.identifier,'2')
                self.answer(adapter,promptId='1')
                self.assertEqual(peer.calls,[])
                self.answer(adapter,promptId='2')
                self.assertEqual(sum(call[0]=='MSG_ANSWER' for call in peer.calls),1)

    def test_expiry_and_next_prompt_during_status_query_cannot_receive_old_answer(self):
        adapter,peer,output=self.setup_adapter()
        self.publish(adapter,peer,message('child#0','Expired'))
        def replace(command):
            self.publish(adapter,peer,{'id':'MSG_NOTIFICATION','fields':{
                'ProcId':'child#0','DataType':'STATUS','ExecutorStatus':'RUNNING'}},
                message('child#0','Next','2'))
        peer.during=replace
        self.answer(adapter,promptId='1')
        self.assertEqual([call[0] for call in peer.calls],['REQ_EXEC_STATUS'])
        self.assertEqual(adapter.prompts.active.identifier,'2')


if __name__=='__main__':
    unittest.main()
