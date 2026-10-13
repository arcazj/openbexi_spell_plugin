"""Keep documented global verification options out of the command-only phase.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES = {
    'spell/lang/helpers/tchelper.py': 'c40677470312d45aa2d28de92ab05aaa116e1d1d6644038dc94957bcbe6c8ec8',
}


def apply(name, raw):
    assert hashlib.sha256(raw).hexdigest() == PREIMAGES[name], name
    source = raw.decode()
    old = "                tcIsSuccess = REGISTRY['TC'].send(self._cmdDef, config = self.getConfig() )"
    assert source.count(old) == 1
    source = source.replace(old, """                tcConfig = self.getConfig()
                if self.__verifyCondition:
                    # LRM 2.4.4 p54 permits global Verify options in Send.
                    # These three options belong to the later TM phase only.
                    # Preserve its full config and all per-condition overrides.
                    tcConfig = dict(tcConfig)
                    for key in (Retries, IgnoreCase, ValueFormat):
                        tcConfig.pop(key, None)
                tcIsSuccess = REGISTRY['TC'].send(self._cmdDef, config=tcConfig)""")
    return source.encode()


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    report = {}
    for name, expected in PREIMAGES.items():
        target = site/name
        raw = target.read_bytes()
        corrected = apply(name, raw)
        for directory, content in (('original', raw), ('patched', corrected)):
            saved = evidence/directory/name
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(content)
        target.write_bytes(corrected)
        report[name] = dict(preimage_sha256=expected, sha256=hashlib.sha256(corrected).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    apply_tree(sys.argv[1], sys.argv[2])
