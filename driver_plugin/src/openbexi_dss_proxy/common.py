# SPDX-License-Identifier: GPL-3.0-or-later
from spell.utils.grpc_utils import PackValue
from spell.lib.adapter.utctime import TIME
from spell.lib.exception import DriverException
import math

# These modifiers govern the original helper's reporting/failure policy.
# Operational modifiers are preserved so the receiving profile can reject them.
POLICY = {'OnFailure','OnTrue','OnFalse','OnSkip','PromptUser','PromptFailure','PromptSuccess','Notify','GiveChoice','HandleError'}


def settings(config):
    return PackValue({k:v for k,v in (config or {}).items() if k not in POLICY})


def timeout_seconds(value):
    """Translate the original TIME contract, which has rel(), not __float__."""
    if isinstance(value, TIME):
        if not value.isRel():
            raise DriverException('Timeout must be relative')
        value = value.rel()
    if type(value) not in {int, float} or not 0 < value <= 30 or not math.isfinite(value):
        raise DriverException('Timeout must be finite and greater than zero, up to 30 seconds')
    return value
