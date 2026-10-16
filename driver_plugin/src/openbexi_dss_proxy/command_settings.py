"""Normalize native SPELL TIME objects before the original protobuf boundary."""
# SPDX-License-Identifier: GPL-3.0-or-later
import math
from spell.lib.adapter.utctime import TIME
from spell.lib.exception import DriverException
from .common import POLICY


def duration(value, name, maximum, *, positive=False):
    if type(value) is str:
        value = TIME(value)
    if isinstance(value,TIME):
        if not value.isRel():
            raise DriverException(name+' must be relative')
        value = value.rel()
    if (type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= maximum
            or (positive and value == 0)):
        raise DriverException('Invalid command '+name)
    return value


def normalize(settings):
    helper_policy = {'Tolerance','AdjLimits','AllowInterrupt','Wait','Delay','Sequence','Confirm'}
    operational = {'Time','ReleaseTime','SendDelay','Timeout','LoadOnly','addInfo','ConfirmCritical','Block','Group'}
    if set(settings) - POLICY - helper_policy - operational:
        raise DriverException('Unqualified command modifier')
    result = {'Timeout':duration(settings.get('Timeout',5),'Timeout',3600,positive=True)}
    for key in ('Block','Group','LoadOnly','ConfirmCritical'):
        if key in settings:
            if type(settings[key]) is not bool:
                raise DriverException(key+' must be boolean')
            if key in ('Block','Group'):
                if settings[key]:
                    raise DriverException('Grouped command protocol is not qualified yet')
            else:
                result[key] = settings[key]
    for key in ('Time','ReleaseTime'):
        if key not in settings:
            continue
        value = settings[key]
        # Original helper/item defaults use zero or an empty string for no tag.
        if type(value) in (int,float,str) and value in (0,''):
            continue
        if type(value) is str:
            value = TIME(value)
        if isinstance(value,TIME):
            if not value.isAbs():
                raise DriverException(key+' must be absolute UTC')
            value = value.abs()
        if type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= (1<<63)/1e9-1:
            raise DriverException('Invalid command '+key)
        result[key] = value
    # The original language.xml uses None to mean no requested send delay.
    if 'SendDelay' in settings and settings['SendDelay'] is not None:
        result['SendDelay'] = duration(settings['SendDelay'],'SendDelay',86400)
    if 'addInfo' in settings:
        if type(settings['addInfo']) is not dict:
            raise DriverException('addInfo must be a dictionary')
        result['addInfo'] = settings['addInfo']
    return result
