"""Checked original Send/WaitFor telemetry handoff corrections.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES = {
    'spell/lang/helpers/tchelper.py': 'efa7ec315be2553050fcb82567d205f458bf6c7899726fbaab92ebb8f9d1ea3e',
    'openbexi_dss_proxy/tm.py': '21c8a9c0bf4927868cd320505d89a3315c03d4afee6d09c727f05982d8857ad6',
}


def apply(name, raw):
    assert hashlib.sha256(raw).hexdigest() == PREIMAGES[name], name
    source = raw.decode()
    if name.endswith('/tchelper.py'):
        old = '            tmIsSuccess = REGISTRY[\'TM\'].verify(self.__verifyCondition, config=self.getConfig())'
        assert source.count(old) == 1
        source = source.replace(old, '''            # The TC phase has already consumed these command-only controls.
            # Keep shared acquisition/comparison/policy options, and do not
            # mutate the caller's config or per-condition TM overrides.
            tmConfig = dict(self.getConfig())
            for key in (Confirm, ConfirmCritical, SendDelay, Sequence, Time,
                        Block, ReleaseTime):
                tmConfig.pop(key, None)
            tmIsSuccess = REGISTRY['TM'].verify(self.__verifyCondition, config=tmConfig)''')
    else:
        old = "'AdjLimits','Retry','Strict','STEP_ID'}"
        assert source.count(old) == 1
        source = source.replace(old, "'AdjLimits','Retry','Strict','STEP_ID','InWaitFor'}")
        old = "    for key in ('Retry', 'Strict'):"
        assert source.count(old) == 1
        source = source.replace(old, "    for key in ('Retry', 'Strict', 'InWaitFor'):")
    return source.encode()


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    report = {}
    for name, expected in PREIMAGES.items():
        path = site / name
        raw = path.read_bytes()
        patched = apply(name, raw)
        for directory, content in (('original', raw), ('patched', patched)):
            saved = evidence / directory / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(content)
        path.write_bytes(patched)
        report[name] = dict(preimage_sha256=expected, sha256=hashlib.sha256(patched).hexdigest())
    (evidence / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    apply_tree(sys.argv[1], sys.argv[2])
