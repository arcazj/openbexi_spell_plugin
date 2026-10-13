"""Retain the qualified donor source identities independently of later reports.

Read exact committed reports, not the mutable canonical evidence paths. These
are source-composition expectations, not acceptance of the combined runtime.
"""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DONORS = {
    'baseline':('fabeaf882966614314ebd799d54eea2b83f020ba','obs'),
    'command':('fabeaf882966614314ebd799d54eea2b83f020ba','cmd'),
    'time_verify':('85bc970ba1da1aa5dc830d70d0e43c786c1b6558','time_verify_review'),
    'ipc':('d9b6be7','dta_ipc_review'),
    'scheduler':('8e4a59a603ae5930814773479dcaa5be958b1520','scheduler'),
    'resource':('42b4f01','resource'),
    'limit':('419b37a434165a66290c0af3f7990201602d62c6','limit'),
    'database':('8a61a2d61e17713170b1629941d8284b74a427a5','database_import'),
    'notification':('aece0cfd8633ff375a42158e8dd717eb74e720e0','notification'),
    'value_units':('6c238b54c9250ce742d76fd0277de671c4780191','value_units'),
    'user_database':('e5f6b070f6bdf178221c75793ce21a81d3c6a559','user_database'),
    'scdb':('e85a2e9b77465ba6865949f3884f41d655840196','scdb'),
    'timing':('bfac147f03ac539114465f5d63b81e40237a3d4a','timing'),
    'child_host':('166caff449f208d41859d41257517fc8fec6f509','child_host_review'),
    'console_input':('15c7dd105a8c3502daf20a38afc73171ce76cb71','console_input_review'),
    'checkpoint_error':('9c674bd51115e016dd135d3ed76c1ebf8a4ed207','checkpoint_error'),
}


def main():
    import sys
    sys.path.insert(0,str(ROOT/'source_port'))
    import integrated_patches as composition
    reports, donors = {}, {}
    for key,(revision,name) in DONORS.items():
        commit = subprocess.check_output(['git','rev-parse',revision],cwd=ROOT,text=True).strip()
        path = 'conformance/evidence/'+name+'.json'
        raw = subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
        reports[key] = json.loads(raw)
        donors[key] = {'commit':commit,'path':path,'sha256':hashlib.sha256(raw).hexdigest()}
    native = dict(reports['time_verify']['native_manifest']['source_hashes'])
    ipc_name = composition.dta_ipc_patches.SOURCE
    native[ipc_name] = reports['ipc']['sources']['manifest']['source_hashes'][ipc_name]
    native.update(reports['scheduler']['runtime_sources']['scheduler_manifest']['source_hashes'])
    recorder = reports['checkpoint_error']['native_overlay']
    if recorder['mode'] != 'fix' or recorder['source'] in native:
        raise ValueError('Unexpected or overlapping recorder donor')
    native[recorder['source']] = {name.removesuffix('_sha256'):value
                                for name,value in recorder['sources'].items()}
    prefix = '/usr/local/lib/python3.13/site-packages/'
    python = {name.removeprefix(prefix):value for name,value in reports['baseline']['runtime_sources']['installed'].items()}
    python.update({name:reports['command']['runtime_sources']['installed'][prefix+name]
                   for name in composition.cmd_patches.PREIMAGES})
    python.update({name:row['sha256'] for name,row in reports['time_verify']['python_manifest'].items()})
    for key,kind in (('resource','resource-conformance-patch'),('limit','limit-patch')):
        python.update({name:row['sha256'] for name,row in reports[key]['runtime_sources']['manifests'][kind].items()})
    python.update(reports['database']['runtime_sources']['installed'])
    python.update(reports['user_database']['runtime_sources']['installed'])
    python.update({name:row['patched_sha256'] for name,row in reports['notification']['runtime_sources']['overlay']['sources'].items()})
    values = reports['value_units']['runtime_sources']['installed']
    python.update({name:values[prefix+name] for name in composition.value_units_patches.PREIMAGES if name.startswith('spell/')})
    driver = {'openbexi_dss_proxy/tm.py':reports['limit']['runtime_sources']['manifests']['limit-patch']['openbexi_dss_proxy/tm.py']['sha256'],
              'openbexi_dss_proxy/tc.py':values[prefix+'openbexi_dss_proxy/tc.py']}
    python.update({name:row['patched_sha256']
                   for name,row in reports['scdb']['runtime_sources']['scdb']['sources'].items()})
    timing = reports['timing']['runtime_sources']['diagnostic_overlay']['overlay']['timing-patch']['manifest']
    for name, row in timing.items():
        outputs = python if name.startswith('spell/') else driver
        if outputs[name] != row['preimage_sha256']:
            raise ValueError('Timing donor chain differs from earlier qualified output: '+name)
        outputs[name] = row['sha256']
    host = {name:value for name,value in reports['child_host']['inputs'].items()
            if name.startswith('host_runtime/python/')}
    console_commit = donors['console_input']['commit']
    client_names = subprocess.check_output(
        ['git','ls-tree','-r','--name-only',console_commit,'host_plugin/src'],cwd=ROOT,text=True).splitlines()
    host_client = {name:hashlib.sha256(subprocess.check_output(
        ['git','show',console_commit+':'+name],cwd=ROOT)).hexdigest()
        for name in client_names if name.endswith('.py')}
    for name,value in reports['console_input']['inputs'].items():
        if name.startswith('host_plugin/src/') and host_client.get(name) != value:
            raise ValueError('Console donor source differs from its exact commit: '+name)
    if set(native) != set(composition.NATIVE_NAMES):
        raise ValueError('Qualified native source set differs from composition')
    result = {'schema':'openbexi.spell.qualified-source-donors/1',
        'scope':'Independent tranche source expectations only; combined runtime behavior remains unqualified.',
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'donors':donors,'native':native,
        'python':{name:python[name] for name in composition.PYTHON_NAMES},'driver':driver,
        'host':host, 'host_client':host_client,
        'full_v05_accepted':False,'full_v06_accepted':False}
    output = ROOT/'distribution/evidence/followup-qualified-sources.json'
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'output':str(output),'native':len(native),'python':len(result['python']),'driver':len(driver)},indent=2))


if __name__ == '__main__':
    main()
