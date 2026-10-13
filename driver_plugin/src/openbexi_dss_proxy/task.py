# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.task import TaskInterface
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import PackValue
from .connection import call
from .common import settings


class Tasks(TaskInterface):
    def _startTask(self,name,arguments,config=None):
        return call('TASK','StartTask',p.Task(name=name,args=PackValue(arguments),config=settings(config))).value

    def _stopTask(self,name,config=None):
        return call('TASK','StopTask',p.Task(name=name,config=settings(config))).value

    def _checkTask(self,name,config=None):
        return call('TASK','CheckTask',p.Task(name=name,config=settings(config))).value

    def _openDisplay(self,name,config=None):
        call('TASK','OpenDisplay',p.Display(name=name,config=settings(config)))

    def _printDisplay(self,name,config=None):
        call('TASK','PrintDisplay',p.Display(name=name,config=settings(config)))

    def _closeDisplay(self,name,config=None):
        call('TASK','CloseDisplay',p.Display(name=name,config=settings(config)))


TASK = Tasks()
