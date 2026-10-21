"""Host-only extension; the original SPELL library lives in the native image."""
# SPDX-License-Identifier: GPL-3.0-or-later
__version__ = '0.7.0'


def describe():
    return {'api': 1, 'id': 'spell', 'label': 'SPELL',
        'runner': 'openbexi_spell_host.runner', 'debugAdapter': 'openbexi_spell_host.dap',
        'gracefulStopMilliseconds': 10000, 'supportsStepOut': False,
        'sourceModules': ['spell', 'libSPELL_DTA_v3'], 'procedureWorkspace': True}
