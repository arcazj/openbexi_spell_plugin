"""A timeout reminder belongs to one still-active native prompt."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from prompts import PromptQueue


def publish(queue, duration='250000', default='False', procedure='main#1'):
    queue.observe({'id':'MSG_PROMPT','fields':{'ProcId':procedure,
        'TimeoutMicroseconds':duration,'DefaultProvided':default}}, ['child#1'])


def test_reminder_deadline_once_without_answering_or_changing_native_prompt():
    now=[100.0]; queue=PromptQueue('main#1',clock=lambda:now[0])
    publish(queue); entry=queue.expose()
    now[0]=100.249; assert queue.reminders()==[]
    now[0]=100.25; assert queue.reminders()==[entry]
    now[0]=200; assert queue.reminders()==[]
    assert queue.active is entry and entry.phase=='active'
    assert queue.begin(entry.identifier) is entry
    queue.before_send(entry);queue.complete(entry)
    assert queue.reminders()==[]


@pytest.mark.parametrize('duration,default',[('0','False'),('0','True'),('250000','True')])
def test_zero_timeout_and_supplied_default_never_remind(duration,default):
    now=[0.0];queue=PromptQueue('main#1',clock=lambda:now[0])
    publish(queue,duration,default);queue.expose();now[0]=1000
    assert queue.reminders()==[]


def test_queued_prompt_reminds_only_when_exposed_and_terminal_prompt_never_reminds():
    now=[0.0];queue=PromptQueue('main#1',clock=lambda:now[0])
    publish(queue);publish(queue,procedure='child#1');first=queue.expose()
    now[0]=1;assert queue.reminders()==[first]
    queue.invalidate('main#1');assert queue.reminders()==[]
    second=queue.expose();assert queue.reminders()==[second]
    queue.observe({'id':'MSG_NOTIFICATION','fields':{
        'ProcId':'child#1','DataType':'STATUS','ExecutorStatus':'ABORTED'}})
    assert queue.reminders()==[]


def test_stale_answer_does_not_consume_reminder_and_retry_preserves_deadline():
    now=[0.0];queue=PromptQueue('main#1',clock=lambda:now[0])
    publish(queue);entry=queue.expose();now[0]=1
    with pytest.raises(ValueError,match='Stale'):queue.begin('unknown')
    queue.begin(entry.identifier);assert queue.reminders()==[]
    queue.cancel(entry);assert queue.reminders()==[entry]


@pytest.mark.parametrize('duration,default',[('-1','False'),('nan','False'),('inf','False'),
    ('bad','False'),('1','invalid'),('1',None)])
def test_malformed_metadata_cannot_publish_prompt(duration,default):
    queue=PromptQueue('main#1')
    with pytest.raises((ValueError,RuntimeError)):publish(queue,duration,default)
    assert queue.pending==[] and queue.active is None


def test_legacy_prompt_without_duration_remains_indefinite():
    queue=PromptQueue('main#1')
    queue.observe({'id':'MSG_PROMPT','fields':{'ProcId':'main#1','Time':'2026-10-16'}})
    queue.expose();assert queue.reminders()==[]
