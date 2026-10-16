"""Checked telemetry deadline extension after the full-limit diagnostic recipe."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path

PREIMAGES = {
    'openbexi_dss_proxy/common.py': '38c8974152772d7d696e565c60ee28ff0b2dce66f640944fabe83cbebdb713f1',
    'openbexi_dss_proxy/tm.py': '9b4c8dc2fb6eb3fa32833aaaea695e629033ba69c8da96e82d8b01d252b8572e',
    'openbexi_spell_dss/transport.py': '8600331ecf4cd475611b172d4a46a01fc0ae8258e7cd1adc3e92edab05ea1d7a',
    'openbexi_spell_dss/command_budget.py': '08d6858bec5f168ff96c7a12b95a111f2a4391a22f0d929a7f788bf230f675da',
    'openbexi_spell_dss/rpc.py': 'bffa43867ea4e95ef881cc17a993e02a8e9c4ebf413d8194eff72fffec908b91',
}


def replace(source, old, new):
    if source.count(old) != 1:raise ValueError('Telemetry patch anchor differs: '+old[:90])
    return source.replace(old, new)


def apply(name, raw):
    if hashlib.sha256(raw).hexdigest() != PREIMAGES[name]:raise ValueError('Telemetry preimage differs: '+name)
    source = raw.decode('utf-8')
    if name == 'openbexi_dss_proxy/common.py':
        source = replace(source, 'def timeout_seconds(value):', 'def timeout_seconds(value, maximum=30):')
        source = replace(source, 'not 0 < value <= 30 or not math.isfinite(value)', 'not 0 < value <= maximum or not math.isfinite(value)')
        source = replace(source, "raise DriverException('Timeout must be finite and greater than zero, up to 30 seconds')",
            "raise DriverException('Timeout must be finite and greater than zero, up to '+str(maximum)+' seconds')")
    elif name == 'openbexi_dss_proxy/tm.py':
        source = replace(source, "timeout_seconds(wire['Timeout'])", "timeout_seconds(wire['Timeout'], maximum=3600)")
    elif name == 'openbexi_spell_dss/command_budget.py':
        source = replace(source, 'def command_budget(family, method, request):', '''def command_budget(family, method, request):
    if family == 'TM' and method == 'RefreshItem':
        from .telemetry_budget import budget
        return budget(request)''')
    elif name == 'openbexi_spell_dss/rpc.py':
        source = replace(source, "self.transport.sample(request.item.mnemonic, wait=settings.get('Wait',False), timeout=settings.get('Timeout',3))",
            "self.transport.sample(request.item.mnemonic, wait=settings.get('Wait',False), timeout=settings.get('Timeout',3), check=check)")
    else:
        source = replace(source, 'def sample(self, name, *, wait=False, timeout=3):', 'def sample(self, name, *, wait=False, timeout=3, check=None):')
        source = replace(source, """        if type(wait) is not bool or type(timeout) not in {int,float} or not 0 < timeout <= 30:
            raise ValueError('Invalid telemetry wait/timeout')
        deadline = time.monotonic() + timeout""", """        from .telemetry_budget import timeout as validate_timeout
        if type(wait) is not bool:raise ValueError('Telemetry Wait must be Boolean')
        validate_timeout(timeout)
        if check is not None:check()
        deadline = time.monotonic() + timeout""")
        source = replace(source, '        while True:\n            if self.error:', '        while True:\n            if check is not None:check()\n            if self.error:')
        source = replace(source, '                return self.telemetry.sample(name)', '                if check is not None:check()\n                return self.telemetry.sample(name)')
    result = source.encode('utf-8');compile(result, name, 'exec')
    return result


def apply_tree(site, evidence):
    site, evidence = Path(site), Path(evidence)
    outputs = {name: apply(name, (site/name).read_bytes()) for name in PREIMAGES}
    report = {}
    for name, output in outputs.items():
        for stage, data in (('original', (site/name).read_bytes()), ('patched', output)):
            path = evidence/stage/name;path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(data)
        (site/name).write_bytes(output)
        report[name] = dict(preimage_sha256=PREIMAGES[name], sha256=hashlib.sha256(output).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    import sys
    apply_tree(sys.argv[1], sys.argv[2])
