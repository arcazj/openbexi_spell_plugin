"""Independent competing native procedure for shared-data atomicity evidence."""
import json
from pathlib import Path
import time
from spell.lang.functions import GetSharedData, SetSharedData
from spell.runtime import ARGS

identity = ARGS['identity']
Path('race-ready-' + str(identity)).write_text('ready')
deadline = time.monotonic()+30
while not Path('race-release').exists():
    assert time.monotonic() < deadline, 'Controller never released race'
    time.sleep(.01)

results = {}
for index in range(8):
    key = 'race-positive-' + str(index)
    results[key] = SetSharedData(Name=key,Value=identity,Expected=0,HandleError=False)
results['boundary'] = SetSharedData(Name='race-boundary',Value=[identity],Expected=[],HandleError=False)
results['failure'] = SetSharedData(Name='race-recovery',Value=identity,Expected=-1,HandleError=False)
results['recovery'] = SetSharedData(Name='race-recovery',Value=identity,Expected=0,HandleError=False)
Path('race-result-' + str(identity) + '.json').write_text(json.dumps(results),encoding='utf-8')
