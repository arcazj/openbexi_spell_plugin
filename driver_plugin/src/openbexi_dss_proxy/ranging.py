# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.ranging import RngInterface
from spell.stubs import SPELLDriver_pb2 as p
from .connection import call
from .common import settings


class Ranging(RngInterface):
    def _enableRanging(self,config):
        return call('RNG','EnableRanging',p.Ranging(config=settings(config))).value

    def _disableRanging(self,config):
        return call('RNG','DisableRanging',p.Ranging(config=settings(config))).value

    def _abortRanging(self,config):
        return call('RNG','AbortRanging',p.Ranging(config=settings(config))).value

    def _startRanging(self,bbe,antenna,config):
        return call('RNG','StartRanging',p.Ranging(bbe=bbe,antenna=antenna,config=settings(config))).value

    def _startCalibration(self,bbe,antenna,config):
        return call('RNG','StartCalibration',p.Ranging(bbe=bbe,antenna=antenna,config=settings(config))).value

    def _getBasebandConfig(self,bbe,param,config):
        return call('RNG','GetBasebandConfig',p.BaseBandConfig(bbe=bbe,param=param,config=settings(config))).value

    def _setBasebandConfig(self,bbe,param,value,config):
        return call('RNG','SetBasebandConfig',p.BaseBandConfig(bbe=bbe,param=param,value=str(value),config=settings(config))).value

    def _getAntennaNames(self,config):
        return list(call('RNG','GetAntennaNames',settings(config)).names)

    def _getRangingPaths(self,config):
        return list(call('RNG','GetRangingPaths',settings(config)).names)

    def _getBasebandNames(self,config):
        return list(call('RNG','GetBasebandNames',settings(config)).names)

    def _getRangingStatus(self,config):
        return call('RNG','GetRangingStatus',settings(config)).value

    def _updateCortexConf(self,config):
        return call('RNG','UpdateCortexConf',settings(config)).value


RNG = Ranging()
