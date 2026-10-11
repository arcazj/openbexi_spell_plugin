"""Load the real DTA extension from the executor's single shared library.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import importlib.util
from pathlib import Path
import sys
from spell_native import launcher

launcher.validate()
if 'libasan.so' not in Path('/proc/self/maps').read_text(encoding='utf-8'):
    raise ImportError('This diagnostic native build requires spell-native-python or spell-native run.')
_path = launcher.ROOT / 'bin/libspell_executor313.so'
_spec = importlib.util.spec_from_file_location(__name__, _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
sys.modules[__name__] = _module
