"""Host audio selection and DAP relay delivery, without producing test sounds."""
import io
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openbexi_spell_host import dap, sound


def test_windows_reminder_uses_host_audio(monkeypatch):
    calls=[]
    monkeypatch.setattr(sound.sys,'platform','win32')
    monkeypatch.setitem(sys.modules,'winsound',SimpleNamespace(MB_ICONEXCLAMATION=48,MessageBeep=calls.append))
    sound.reminder();assert calls==[48]


@pytest.mark.parametrize('platform',['linux','win32'])
def test_terminal_fallback_keeps_session_available(monkeypatch,platform):
    def unavailable(_):raise RuntimeError('No audio device')
    stream=io.StringIO();monkeypatch.setattr(sound.sys,'platform',platform)
    monkeypatch.setattr(sound.sys,'stderr',stream)
    monkeypatch.setitem(sys.modules,'winsound',SimpleNamespace(MB_ICONEXCLAMATION=48,MessageBeep=unavailable))
    sound.reminder();assert stream.getvalue()=='\a'


def test_dap_relay_sounds_and_forwards_same_prompt_notification(monkeypatch):
    frames=[{'type':'event','event':'openbexi/promptReminder','body':{'promptId':'3','procedureId':'child#1'}},
        {'type':'event','event':'output','body':{'output':'still waiting'}}]
    incoming=iter([*frames,None]);sent=[];sounds=[];closed=[]
    process=SimpleNamespace(stdout=io.BytesIO(),wait=lambda timeout:0)
    class Container:
        def __init__(self,*args):pass
        def start(self,**kwargs):return process
        def close(self):closed.append(True)
    monkeypatch.setattr(dap,'runtime',Container)
    monkeypatch.setattr(dap,'read',lambda stream:next(incoming))
    monkeypatch.setattr(dap,'write',lambda stream,message:sent.append(message))
    monkeypatch.setattr(dap,'reminder',lambda:sounds.append(True))
    monkeypatch.setattr(dap.sys,'argv',['dap','--project','.'])
    for name in ('stdin','stdout','stderr'):
        monkeypatch.setattr(dap.sys,name,SimpleNamespace(buffer=io.BytesIO()))
    assert dap.main()==0
    assert sounds==[True] and sent==frames and closed==[True]
