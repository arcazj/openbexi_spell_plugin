# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.tc import TcInterface
from spell.lib.adapter.tc_item import TcItemClass
from spell.lib.exception import DriverException
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import PackValue
from .connection import call
from .common import POLICY, timeout_seconds


def descriptor(item,config):
    settings = dict(config or {},**item.getConfig())
    if settings.get('Block'):
        raise DriverException('Atomic command blocks are not qualified in this driver profile')
    # Send_Helper consumes verification/reporting policy before/after injection.
    helper_policy = {'Tolerance','AdjLimits','ConfirmCritical','AllowInterrupt','Wait','Delay','Sequence'}
    if set(settings) - POLICY - helper_policy - {'Time','SendDelay','ReleaseTime','Timeout','Confirm','Block'}:
        raise DriverException('Unqualified command modifier')
    for key in ('Time','SendDelay','ReleaseTime'):
        if settings.get(key):
            raise DriverException('Scheduled TC is not qualified in this driver profile')
    args = []
    for parameter in item._getParams():
        value = parameter.value
        if value.units():
            raise DriverException('Command units require explicit catalog conversion')
        args.append([parameter.name,value.get(),dict(ValueFormat=value.format(),Radix=value.radix(),ValueType=value.vtype())])
    timeout = timeout_seconds(settings.get('Timeout',5))
    return p.CommandDesc(command=p.TcItemDesc(mnemonic=item.name(),description=item.desc()),args=PackValue(args),config=PackValue({'Timeout':timeout}))


class Commands(TcInterface):
    def _createTcItem(self,mnemonic,description=''):
        row = call('TC','CreateTcItem',p.TcItemDesc(mnemonic=mnemonic,description=description))
        return TcItemClass(self,row.mnemonic,row.description)

    def _sendCommand(self,item,config=None):
        success = call('TC','SendCommand',descriptor(item,config)).value
        item._setExecutionStageStatus('ONBOARD_EXECUTION' if success else 'DSS_REJECTED','SUCCEEDED' if success else 'FAILED')
        item._setCompleted(success)
        return success

    def _sendList(self,items,config=None):
        # Separate item receipts preserve truthful per-member status.
        for item in items:
            if not self._sendCommand(item,config):
                return False
        return True

    def _sendBlock(self,items,config=None):
        raise DriverException('Atomic command blocks are not qualified in this driver profile')


TC = Commands()
