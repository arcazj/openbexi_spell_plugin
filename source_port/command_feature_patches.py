"""Exact-source integration of individual command scheduling and load-only RPC."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys

PREIMAGES = {'openbexi_spell_dss/rpc.py': 'e28effbb3c580149b4e031b7f4f9336dee007728f44bce8c128e25a6a260dc63', 'openbexi_dss_proxy/tc.py': '19e24099b2b132764d83c8429eb3af5c794745b8bfbd07ccd4d1e48a7ae53651', 'openbexi_dss_proxy/connection.py': 'a8097827a1ebdc7d4d58858a3d6f211af65fba779ee0d9f4962827dde4c7ad0f', 'openbexi_spell_dss/relay.py': 'a28a694a5da00b57e4f77bcf68a99323d872a6eff890c21ec4dad572d4955c5e'}


def replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Command feature patch anchor differs: '+old[:80])
    return source.replace(old,new)


def apply(name, raw):
    if hashlib.sha256(raw).hexdigest() != PREIMAGES[name]:
        raise ValueError('Command feature preimage differs: '+name)
    source = raw.decode('utf-8')
    if name == 'openbexi_spell_dss/rpc.py':
        start = source.index("        if family == 'TC' and method in {'SendCommand','SendList','SendBlock'}:")
        end = source.index("        if family == 'PCS':", start)
        source = source[:start] + '''        if family == 'TC' and method in {'SendCommand','SendList','SendBlock'}:
            from .command_rpc import prepare
            return prepare(self, method, request, identity, request_id, check)
''' + source[end:]
        source = replace(source,"result.stage.append('ONBOARD_EXECUTION' if success else 'DSS_REJECTED')",
                         "result.stage.append(('LOADING' if config(rows[len(result.stage)].config).get('LoadOnly') else 'ONBOARD_EXECUTION') if success else 'DSS_REJECTED')")
    elif name == 'openbexi_dss_proxy/tc.py':
        source = replace(source,'from .common import POLICY, timeout_seconds',
                         'from .command_settings import normalize')
        start = source.index("    if settings.get('Block'):")
        end = source.index('    args = []',start)
        source = source[:start] + '    options = normalize(settings)\n' + source[end:]
        source = replace(source,"    timeout = timeout_seconds(settings.get('Timeout',5))\n",'')
        source = replace(source,"config=PackValue({'Timeout':timeout})",'config=PackValue(options)')
        source = replace(source,"        success = call('TC','SendCommand',descriptor(item,config)).value",'''        request = descriptor(item,config)
        success = call('TC','SendCommand',request).value
        load_only = normalize(dict(config or {},**item.getConfig())).get('LoadOnly',False)''')
        source = replace(source,"item._setExecutionStageStatus('ONBOARD_EXECUTION' if success else 'DSS_REJECTED','SUCCEEDED' if success else 'FAILED')",
                         "item._setExecutionStageStatus(('LOADING' if load_only else 'ONBOARD_EXECUTION') if success else 'DSS_REJECTED',('LOADED' if load_only else 'SUCCEEDED') if success else 'FAILED')")
    elif name == 'openbexi_dss_proxy/connection.py':
        source = replace(source,'import grpc\n','import grpc\nfrom openbexi_spell_dss.command_budget import command_budget\n')
        source = replace(source,'return getattr(stub,method)(request,timeout=34)',
                         'return getattr(stub,method)(request,timeout=command_budget(family,method,request)+4)')
    elif name == 'openbexi_spell_dss/relay.py':
        source = replace(source,'from .server import Server\n','from .server import Server\nfrom .command_budget import relay_budget\n')
        source = replace(source,'        identity = uuid.uuid4().hex','        budget = relay_budget(path,raw)\n        identity = uuid.uuid4().hex')
        source = replace(source,'answer = inbox.get(timeout=35)','answer = inbox.get(timeout=budget+5)')
    else:
        raise ValueError('Unknown command integration source')
    result = source.encode('utf-8')
    compile(result,name,'exec')
    return result


def apply_tree(site, evidence):
    site,evidence = Path(site),Path(evidence)
    manifest = {}
    for name,expected in PREIMAGES.items():
        path = site/name
        original = path.read_bytes()
        patched = apply(name,original)
        for label,content in (('original',original),('patched',patched)):
            target = evidence/label/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(content)
        path.write_bytes(patched)
        manifest[name] = dict(preimage_sha256=expected,sha256=hashlib.sha256(patched).hexdigest())
    (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    apply_tree(*sys.argv[1:])
