# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.gcstime import TimeInterface
from datetime import datetime
from spell.utils.grpc_utils import PackValue
from .connection import call


class Clock(TimeInterface):
    def _getUTC(self,config=None):
        # The original TimeInterface returns datetime; TIME(NOW) consumes it.
        return datetime.fromisoformat(call('TIME','GetUTC',PackValue({})).timeMsg)


TIME = Clock()
