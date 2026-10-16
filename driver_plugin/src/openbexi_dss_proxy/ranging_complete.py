"""Encode original ranging forms into the unchanged original protobuf RPCs."""
# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.exception import DriverException
from spell.lang.constants import IDLE,RANGING,CALIBRATING,ERROR
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import UnpackValue,PackValue
from .connection import call


def operation(method,bbe,antenna,config):
    from .ranging import ranging_settings
    wire=UnpackValue(ranging_settings(config))
    if 'Paths' in wire:raise DriverException('Paths is reserved for the original dual ranging form')
    if type(bbe) is list or type(antenna) is list:
        if type(bbe) is not list or type(antenna) is not list or len(bbe)!=len(antenna) or not 1<=len(bbe)<=2:
            raise DriverException('Invalid dual ranging paths')
        if any(type(v) is not str for v in bbe+antenna):raise DriverException('Ranging path names must be strings')
        wire['Paths']=[list(pair) for pair in zip(bbe,antenna)]
        bbe=antenna=''
    return call('RNG',method,p.Ranging(bbe=bbe,antenna=antenna,config=PackValue(wire))).value


def configure(bbe,param,value,config):
    from .ranging import ranging_settings
    wire=UnpackValue(ranging_settings(config))
    if 'Parameters' in wire:raise DriverException('Parameters is reserved for the original batch form')
    if type(param) is list or type(value) is list:
        if type(param) is not list or type(value) is not list or len(param)!=len(value) or not 1<=len(param)<=2:
            raise DriverException('Invalid baseband batch')
        if any(type(v) is not str for v in param):raise DriverException('Baseband parameter names must be strings')
        wire['Parameters']=[[key,str(item)] for key,item in zip(param,value)]
        param=value=''
    return call('RNG','SetBasebandConfig',p.BaseBandConfig(bbe=bbe,param=param,value=str(value),config=PackValue(wire))).value


def status(value):
    meanings={'READY':IDLE,'RANGING':RANGING,'CALIBRATING':CALIBRATING,'ERROR':ERROR}
    if value not in meanings:raise DriverException('Unknown ranging status')
    return meanings[value]
