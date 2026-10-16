"""Two declared GENERIC ranging paths, with atomic validated operations."""
# SPDX-License-Identifier: GPL-3.0-or-later
from google.protobuf.wrappers_pb2 import BoolValue,StringValue
from .stubs import SPELLDriver_pb2 as p

PATHS=(('DSS-BBE-1','DSS-ANTENNA-1'),('DSS-BBE-2','DSS-ANTENNA-2'))
DEFAULTS={'frequency_hz':'1000000','integration_ms':'1000'}
STATES={'READY','RANGING','CALIBRATING','ERROR'}


def paths(value):
    if type(value) is not list or not 1<=len(value)<=2:
        raise ValueError('Select one or two complete virtual ranging paths')
    for pair in value:
        if type(pair) is not list or len(pair)!=2 or any(type(v) is not str for v in pair) or tuple(pair) not in PATHS:
            raise ValueError('Unknown virtual ranging path')
    if len({pair[0] for pair in value})!=len(value) or len({pair[1] for pair in value})!=len(value):
        raise ValueError('Ranging paths must use distinct basebands and antennas')
    return [list(pair) for pair in value]


def initialize(state):
    """Extend this epoch's legacy profile without resetting its active work."""
    if state.get('ranging') not in STATES or type(state.get('ranging_schedule_enabled')) is not bool:
        raise ValueError('Invalid ranging state')
    bands=state.get('baseband')
    if type(bands) is not dict:raise ValueError('Invalid baseband configuration')
    for bbe,_ in PATHS:bands.setdefault(bbe,dict(DEFAULTS))
    if 'ranging_paths' not in state:
        state['ranging_paths']=[list(PATHS[0])] if state['ranging'] in {'RANGING','CALIBRATING'} else []
    active=state['ranging_paths']
    if active:paths(active)
    elif type(active) is not list:raise ValueError('Invalid active ranging paths')
    if (state['ranging']=='READY' and active) or (state['ranging'] in {'RANGING','CALIBRATING'} and not active):
        raise ValueError('Ranging activity and active paths disagree')


def parameters(value):
    if type(value) is not list or not 1<=len(value)<=len(DEFAULTS):
        raise ValueError('Select one or two virtual baseband parameters')
    result={}
    for pair in value:
        if type(pair) is not list or len(pair)!=2:
            raise ValueError('Malformed virtual baseband parameter pair')
        key,item=pair
        if type(key) is not str or key not in DEFAULTS or key in result:
            raise ValueError('Unknown or duplicate virtual baseband parameter')
        if type(item) is not str or not item.isascii() or not item.isdigit() or len(item)>10 or not 1<=int(item)<=1000000000:
            raise ValueError('Invalid virtual baseband integer')
        result[key]=item
    return result


def prepare(ground,method,request,settings,check):
    wire=dict(settings)
    if method=='UpdateCortexConf':
        if wire:raise ValueError('Unsupported virtual ranging modifier')
        raise NotImplementedError('GENERIC has no vendor Cortex device')
    if method in {'GetAntennaNames','GetBasebandNames','GetRangingPaths','GetRangingStatus'}:
        if wire:raise ValueError('Unsupported virtual ranging modifier')
        if method=='GetRangingStatus':
            def status():
                value=ground.state()['ranging']
                if value not in STATES:raise ValueError('Invalid ranging state')
                return StringValue(value=value)
            return status
        values={'GetAntennaNames':[v[1] for v in PATHS],
                'GetBasebandNames':[v[0] for v in PATHS],
                'GetRangingPaths':['/'.join(v) for v in PATHS]}
        return lambda:p.Names(names=values[method])
    if method in {'GetBasebandConfig','SetBasebandConfig'}:
        if request.bbe not in {v[0] for v in PATHS}:raise ValueError('Unknown virtual baseband')
        if method=='GetBasebandConfig':
            # This declared profile stores engineering units already: RAW/ENG
            # calibration is identity for Hz and milliseconds, with string RPCs.
            if set(wire)-{'ValueFormat'} or wire.get('ValueFormat','Eng format') not in {'Raw format','Eng format','Default format'}:
                raise ValueError('Unsupported baseband value format or modifier')
            if request.param not in DEFAULTS:raise ValueError('Unknown virtual baseband parameter')
            return lambda:p.BaseBandConfig(bbe=request.bbe,param=request.param,
                value=ground.state()['baseband'][request.bbe][request.param])
        if 'Parameters' in wire:
            if set(wire)!={'Parameters'} or request.param or request.value:
                raise ValueError('Ambiguous baseband batch request')
            updates=parameters(wire['Parameters'])
        else:
            if wire:raise ValueError('Unsupported virtual ranging modifier')
            updates=parameters([[request.param,request.value]])
        def configure():
            check()
            ground.update(lambda state:state['baseband'][request.bbe].update(updates))
            return BoolValue(value=True)
        return configure
    states={'AbortRanging':'READY','StartRanging':'RANGING','StartCalibration':'CALIBRATING'}
    schedules={'EnableRanging':True,'DisableRanging':False}
    if method not in states and method not in schedules:raise NotImplementedError('RNG.'+method)
    selected=[]
    if method in {'StartRanging','StartCalibration'}:
        if 'Paths' in wire:
            if set(wire)!={'Paths'} or request.bbe or request.antenna:
                raise ValueError('Ambiguous dual ranging request')
            selected=paths(wire['Paths'])
        else:
            if wire:raise ValueError('Unsupported virtual ranging modifier')
            selected=paths([[request.bbe,request.antenna]])
    elif wire or request.bbe or request.antenna:
        raise ValueError('Unexpected schedule or abort argument')
    def transition():
        check()
        def update(state):
            if method in schedules:state['ranging_schedule_enabled']=schedules[method]
            else:
                state['ranging']=states[method]
                state['ranging_paths']=[list(pair) for pair in selected]
        ground.update(update)
        return BoolValue(value=True)
    return transition
