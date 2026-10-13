"""Actual procedure effects for the independent native notification observer."""
import json
from pathlib import Path
from spell.lang.functions import Display, GetSharedData, SetSharedData
from spell.lib.exception import DriverException

observed = {}
for dimension in ('positive', 'boundary', 'failure', 'recovery'):
    visible = 'COMMON_VISIBLE_' + dimension
    hidden = 'COMMON_HIDDEN_' + dimension
    Display(visible)
    Display(hidden, Verbosity=999, Notify=False)
    assert SetSharedData(Name=hidden, Value=42, Notify=False, Verbosity=999)
    assert GetSharedData(hidden, Notify=False, Verbosity=999) == 42
    if dimension in ('failure', 'recovery'):
        try:
            GetSharedData(hidden + '_absent', Notify=False, Verbosity=999, HandleError=False)
        except DriverException:
            observed[dimension + '_error'] = 'DriverException'
        else:
            raise AssertionError('Silent operation concealed failure')
    assert SetSharedData(Name=visible, Value=42, Notify=True)
    assert GetSharedData(visible, Notify=True) == 42
    if dimension == 'boundary':
        # A per-call setting must not persist to the next, default-valued call.
        Display('COMMON_RESTORED_boundary')
        assert SetSharedData(Name='COMMON_RESTORED_boundary', Value=43)
    observed[dimension] = 42
Path('silence-effects.json').write_text(json.dumps(observed), encoding='utf-8')
