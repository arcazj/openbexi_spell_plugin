# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.pcs import PcsInterface
from spell.lib.adapter.pcs_item import PtcItemClass
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import UnpackValue
from .connection import call
from .common import settings
from .tc import descriptor


class Pcs(PcsInterface):
    def _createPtcItem(self,mnemonic,description=''):
        row = call('PCS','CreatePtcItem',p.PtcItemDesc(mnemonic=mnemonic,description=description))
        return PtcItemClass(self,row.mnemonic,row.description)

    def _PCS_GetStatus(self,config=None):
        return UnpackValue(call('PCS','PCS_GetStatus',settings(config)))

    def _PCS_isArqEnabled(self,config=None):
        return call('PCS','PCS_IsArqEnabled',settings(config)).value

    def _PCS_isVerifyModeEnabled(self,config=None):
        return call('PCS','PCS_IsVerifyModeEnabled',settings(config)).value

    def _PCS_ReadyToCommand(self,config=None):
        return call('PCS','PCS_ReadyToCommand',settings(config)).value

    def _PCS_AbortPtc(self,config=None):
        return call('PCS','PCS_AbortPtc',settings(config)).value

    def _PCS_Control(self,item,config=None):
        command = descriptor(item,config)
        return call('PCS','PCS_Control',p.PtcDesc(command=p.PtcItemDesc(mnemonic=command.command.mnemonic),
                    args=command.args,config=command.config))

    def _sendPtcCommand(self,item,config=None):
        command = descriptor(item,config)
        reply = call('PCS','SendPtcCommand',p.PtcDesc(command=p.PtcItemDesc(mnemonic=command.command.mnemonic),
                    args=command.args,config=command.config))
        if len(reply.success) != 1:
            raise ValueError('PCS command result count differs')
        item._setExecutionStageStatus(reply.stage[0],'SUCCEEDED' if reply.success[0] else 'FAILED')
        item._setCompleted(reply.success[0])
        return {key:list(getattr(reply,key)) for key in ('code','success','stage','data','error')}

    def _sendPtcList(self,items,config=None):
        result = {key:[] for key in ('code','success','stage','data','error')}
        for item in items:
            row = self._sendPtcCommand(item,config)
            for key in result:
                result[key].extend(row[key])
            if not all(row['success']):
                break
        return result


PCS = Pcs()
