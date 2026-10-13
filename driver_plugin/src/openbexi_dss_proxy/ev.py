# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.ev import EvInterface
from spell.stubs.SPELLDriver_pb2 import Event
from spell.utils.grpc_utils import PackValue
from .connection import call


class Events(EvInterface):
    def _raiseEvent(self,message,config=None):
        settings = {k:v for k,v in (config or {}).items() if k in {'Severity','Scope'}}
        call('EV','RaiseEvent',Event(message=message,config=PackValue(settings)))


EV = Events()
