"""Checked limit profile extension after the accepted Group/Block composition."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path

PREIMAGES = {'openbexi_spell_dss/rpc.py': '816152c5a6ddbcb8509cea9ec10b94254be2c2b42e50026b23b04f7ffa47a179'}


def apply(name, raw):
    if hashlib.sha256(raw).hexdigest() != PREIMAGES[name]:
        raise ValueError('Limit feature preimage differs: '+name)
    source = raw.decode('utf-8')
    anchor = "        if family == 'TM' and method in {'SetLimits','GetLimits','IsAlarmed','InjectItem','RestoreNormalLimits'}:"
    if source.count(anchor) != 1:raise ValueError('Limit dispatch anchor differs')
    source = source.replace(anchor, """        if family == 'TM' and method in {'SetLimits', 'GetLimits', 'IsAlarmed', 'RestoreNormalLimits'}:
            from .limits import Limits
            def acquire(name):
                check()
                return self.prepare('TM', 'RefreshItem', p.TmItemValue(item=p.TmItemDesc(mnemonic=name)),
                                    identity, request_id, check)()
            return Limits(self, acquire).prepare(method, request, check)
"""+anchor)
    result = source.encode('utf-8')
    compile(result, name, 'exec')
    return result


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    outputs = {name: apply(name, (site/name).read_bytes()) for name in PREIMAGES}
    report = {}
    for name, output in outputs.items():
        for label, content in (('original', (site/name).read_bytes()), ('patched', output)):
            path = evidence/label/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (site/name).write_bytes(output)
        report[name] = dict(preimage_sha256=PREIMAGES[name], sha256=hashlib.sha256(output).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report
