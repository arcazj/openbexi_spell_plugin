# SPDX-License-Identifier: GPL-3.0-or-later
from spell.utils.grpc_utils import PackValue

# These modifiers govern the original helper's reporting/failure policy.
# Operational modifiers are preserved so the receiving profile can reject them.
POLICY = {'OnFailure','OnTrue','OnFalse','OnSkip','PromptUser','PromptFailure','PromptSuccess','Notify','GiveChoice','HandleError'}


def settings(config):
    return PackValue({k:v for k,v in (config or {}).items() if k not in POLICY})
