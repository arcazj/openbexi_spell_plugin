"""One-hour telemetry waits with consistent transport and original RPC bounds."""
# SPDX-License-Identifier: GPL-3.0-or-later
import math
from .codec import unpack

MAX_TIMEOUT = 3600


def timeout(value):
    if type(value) not in (int, float) or not 0 < value <= MAX_TIMEOUT or (type(value) is float and not math.isfinite(value)):
        raise ValueError('Telemetry timeout must be finite and greater than zero, up to 3600 seconds')
    return value


def budget(request):
    settings = unpack(request.config) if request.config.type_url else {}
    if type(settings) is not dict or set(settings)-{'Wait', 'Timeout', 'ValueFormat'}:
        raise ValueError('Invalid telemetry RPC configuration')
    if type(settings.get('Wait', False)) is not bool:
        raise ValueError('Telemetry Wait must be Boolean')
    return max(30, timeout(settings.get('Timeout', 3)))
