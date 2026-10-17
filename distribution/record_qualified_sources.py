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
    'database_values':('a494986733ce6f4ceefda41684824f12bfbc5660','database_values'),
    'scdb':('e85a2e9b77465ba6865949f3884f41d655840196','scdb'),
    'timing':('bfac147f03ac539114465f5d63b81e40237a3d4a','timing'),
    'send_verify':('231700dbeabe46ad3f488dc0db33fdc460860889','send_verify'),
    'child_host':('166caff449f208d41859d41257517fc8fec6f509','child_host_review'),
    'console_input':('15c7dd105a8c3502daf20a38afc73171ce76cb71','console_input_review'),
    'host_upgrade':('4a4c8c915ca7379af3a868269a40559f933e4fed','distribution/evidence/host-console-upgrade.json'),
    'checkpoint_error':('9c674bd51115e016dd135d3ed76c1ebf8a4ed207','checkpoint_error'),
    'checkpoint_identity':('53afd40d46fa1e1c0e116de877a48f2f43ca9060','checkpoint_identity'),
    'shutdown_pause':('a97118ea78011205db886e8a9556220201809960','shutdown_pause_review'),
    'child_lifecycle':('4543128e93d7c8a6ee8b27e595f34fe6d5831a65','child_lifecycle'),
    'prompt_timeout':('8a89ba8','prompt_timeout'),
    'prompt_controls':('2d3cd53637675be73544bcb60a843bbc534ee939','prompt_controls'),
    'rng':('922d578','rng'),
    'rng_state':('669c1d7','rng_state'),
    'context_startup':('f843cb8','context_startup_review'),
    'ipc_mailbox':('463e34f','ipc_mailbox'),
    'legacy_compare':('fc44409cd5493ca0ad6e924b2b45d01d34387b6d','legacy_compare'),
    'context_snapshot':('342b1f12ad6c315a686581b64455c250c8d1d08b','context_snapshot'),
    'prompt_startup':('39c652686b20da4cd179712abce16fe4df8e9699','prompt_startup'),
    'wait_interrupt':('728d9ba4fc154f7bbb924233d3b67e8fa7043de0','wait_interrupt'),
    'proc_dictionary':('c22ba3d0f5e2362c2384f09036bfff30e83080b1','proc_dictionary'),
    'display_commands':('f602418','distribution/evidence/group-block-native-review.json'),
    'manoeuvre':('0f566ee','manoeuvre_database_review'),
    'procedure_library':('a8e2bcd','procedure_library_review'),
    'send_complete':('5f2ff9f6ddaa866b36ef4d1785fd424cc5278878','send_complete_review'),
    'database_formats':('3f361e3c547056cbed7aa7e7ea8071b4b690a970','database_format_review'),
    'memory_complete':('a6341664249fbc56669172a197d5d6f2fe89d157','memory_complete_review'),
    'ranging_complete':('4b59f752116135ebb6cb72a49c535efa5f2ea165','ranging_complete_review'),
}


def main():
    import sys
    sys.path.insert(0,str(ROOT/'source_port'))
    import integrated_patches as composition
    reports, donors = {}, {}
    for key,(revision,name) in DONORS.items():
        commit = subprocess.check_output(['git','rev-parse',revision],cwd=ROOT,text=True).strip()
        path = name if '/' in name else 'conformance/evidence/'+name+'.json'
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
    identity = reports['checkpoint_identity']['runtime_sources']['identity_overlay']
    if identity['mode'] != 'identity':
        raise ValueError('Unexpected checkpoint identity donor profile')
    context_name = composition.checkpoint_context_patches.SOURCE
    interpreter_name = composition.checkpoint_identity_patches.SOURCE
    if set(identity['sources']) != {context_name, interpreter_name, recorder['source']}:
        raise ValueError('Unexpected checkpoint identity native source set')
    for name, row in identity['sources'].items():
        expected = {key.removesuffix('_sha256'):value for key,value in row.items()}
        if name == context_name:
            if native[name]['original'] != expected['original'] or native[name]['patched'] != expected['ported']:
                raise ValueError('Context recovery donor preimage differs from qualified DATA output')
            native[name]['patched'] = expected['patched']
        elif name == interpreter_name:
            if name in native:
                raise ValueError('Unexpected earlier interpreter identity correction')
            native[name] = expected
        elif native[name] != expected:
            raise ValueError('Identity donor recorder differs from qualified recorder output')
    for recipe in ('checkpoint_identity_patches.py', 'checkpoint_context_patches.py', 'checkpoint_error_patches.py'):
        committed = subprocess.check_output(['git','show',donors['checkpoint_identity']['commit']+':source_port/'+recipe],cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != identity['recipes'][recipe]:
            raise ValueError('Checkpoint identity recipe differs from its exact donor commit: '+recipe)
    shutdown = reports['shutdown_pause']
    if not shutdown['passed'] or composition.shutdown_pause_patches.SOURCE in native:
        raise ValueError('Unexpected or overlapping shutdown cancellation donor')
    native[composition.shutdown_pause_patches.SOURCE] = {
        key.removesuffix('_sha256'):value for key,value in shutdown['source'].items()}
    recipe = 'source_port/shutdown_pause_patches.py'
    committed = subprocess.check_output(['git','show',donors['shutdown_pause']['commit']+':'+recipe],cwd=ROOT)
    if hashlib.sha256(committed).hexdigest() != shutdown['inputs'][recipe]:
        raise ValueError('Shutdown recipe differs from qualified donor')
    child = reports['child_lifecycle']['runtime_sources']['child_lifecycle_overlay']
    recipe = 'source_port/child_lifecycle_patches.py'
    committed = subprocess.check_output(['git','show',donors['child_lifecycle']['commit']+':'+recipe],cwd=ROOT)
    if hashlib.sha256(committed).hexdigest() != child['recipes']['child_lifecycle_patches.py']:
        raise ValueError('Child lifecycle recipe differs from qualified donor')
    for name, hashes in child['sources'].items():
        expected = {key.removesuffix('_sha256'):value for key,value in hashes.items()}
        if name == composition.shutdown_pause_patches.SOURCE:
            if any(native[name][key] != expected[key] for key in ('original','ported')):
                raise ValueError('Child and shutdown donors have different source bases')
            # Reviewed union of their disjoint blocks, not a runtime acceptance.
            # Undoing forcePause reproduces the exact qualified child source.
            if expected['patched'] != '4caf451be4eb5efd28ac02c7d745ab0fdbddd7a484d904fc6a887b7dad3f298e':
                raise ValueError('Unexpected child context source')
            native[name]['patched'] = 'e8d1c0ed2ee9b66894add739f3b0a0f880a1a2f59bc50034dde5050117fec598'
        elif name in native:
            raise ValueError('Unexpected overlapping child source: '+name)
        else:
            native[name] = expected
    prompt = reports['prompt_timeout']
    if (prompt['passed'] is not True or len(prompt['checks']) != 10
            or any(row['passed'] is not True for row in prompt['checks'].values())
            or prompt['qualified_contracts'] != ['CMP-LRM244-EXAMPLE-118']):
        raise ValueError('Prompt donor lacks complete native observations')
    prompt_sources = prompt['runtime_sources']['integrated']['manifest']['composition']['native']
    recipe = 'prompt_timeout_patches.py'
    committed = subprocess.check_output(['git','show',donors['prompt_timeout']['commit']+':source_port/'+recipe],cwd=ROOT)
    if hashlib.sha256(committed).hexdigest() != prompt_sources['recipes'][recipe]['sha256']:
        raise ValueError('Prompt recipe differs from its qualified commit')
    stages = [stage for stage in prompt_sources['stages'] if stage['recipe'] == recipe]
    changed = {name:row for stage in stages for name,row in stage['sources'].items()}
    if set(changed) != set(composition.prompt_timeout_patches.PREIMAGES):
        raise ValueError('Prompt source set differs from its qualified composition')
    for name, stage in changed.items():
        hashes = {key.removesuffix('_sha256'):value
                  for key,value in prompt_sources['sources'][name].items()}
        if name in native:
            if (native[name]['original'] != hashes['original']
                    or native[name]['ported'] != hashes['ported']
                    or native[name]['patched'] != stage['before_sha256']):
                raise ValueError('Prompt correction overlaps an unexpected donor: '+name)
        elif hashes['ported'] != stage['before_sha256']:
            raise ValueError('Prompt header has an unexpected predecessor')
        if hashes['patched'] != stage['after_sha256']:
            raise ValueError('Prompt composition output differs from its qualified stage')
        native[name] = hashes
    controls = reports['prompt_controls']
    recipe = 'prompt_control_patches.py'
    if controls['passed'] is not True or controls['qualified_contracts'] != []:
        raise ValueError('Prompt control donor lacks independent native controls')
    committed = subprocess.check_output(
        ['git','show',donors['prompt_controls']['commit']+':source_port/'+recipe],cwd=ROOT)
    if hashlib.sha256(committed).hexdigest() != controls['recipe']['sha256']:
        raise ValueError('Prompt control recipe differs from its qualified commit')
    changed = {}
    for stage in controls['native_stages']:
        if stage['recipe'] != recipe or set(changed) & set(stage['sources']):
            raise ValueError('Unexpected prompt control composition stage')
        changed.update(stage['sources'])
    if set(changed) != set(composition.prompt_control_patches.PREIMAGES):
        raise ValueError('Prompt control source set differs from its qualified composition')
    for name, stage in changed.items():
        hashes = {key.removesuffix('_sha256'):value
                  for key,value in controls['native_sources'][name].items()}
        original, before = composition.prompt_control_patches.PREIMAGES[name]
        if hashes['original'] != original or stage['before_sha256'] != before:
            raise ValueError('Prompt control donor preimage differs: '+name)
        if name in native:
            if (any(native[name][key] != hashes[key] for key in ('original','ported'))
                    or native[name]['patched'] != stage['before_sha256']):
                raise ValueError('Prompt control overlaps an unexpected donor: '+name)
        elif hashes['ported'] != stage['before_sha256']:
            raise ValueError('Prompt control IPC source has an unexpected predecessor')
        if hashes['patched'] != stage['after_sha256']:
            raise ValueError('Prompt control output differs from its qualified stage')
        native[name] = hashes
    startup = reports['prompt_startup']
    recipe = 'prompt_startup_patches.py'
    committed = subprocess.check_output(
        ['git','show',donors['prompt_startup']['commit']+':source_port/'+recipe],cwd=ROOT)
    name = composition.prompt_startup_patches.SOURCE
    if (startup['passed'] is not True or startup['qualified_contracts'] != []
            or startup['passed_checks'] != dict(early=40,lifecycle=6,removed=4,reopen=4,
                modes=9,abort=12,timeout=10,duplicate=24)
            or hashlib.sha256(committed).hexdigest() != startup['recipes'][recipe]
            or (startup['original_sha256'],startup['preimage_sha256']) != composition.prompt_startup_patches.PREIMAGES[name]
            or startup['source'] != name or native[name]['patched'] != startup['preimage_sha256']
            or native[name]['original'] != startup['original_sha256']):
        raise ValueError('Prompt transition donor lacks native controls or expected predecessor')
    probes = startup['probes']['probes']
    if set(probes) != {'original','patched'}:
        raise ValueError('Prompt transition donor lacks both differential controls')
    for label, row in probes.items():
        if (row['exit_code'] != (0 if label=='patched' else 1)
                or row['observation'] != {kind:dict(ack_during_transition=label=='patched',
                    winner_preserved=True) for kind in ('startup','cancel')}):
            raise ValueError('Prompt transition differential acknowledgement controls differ')
    native[name]['patched'] = startup['patched_sha256']
    mailbox = reports['ipc_mailbox']
    recipe = 'ipc_mailbox_patches.py'
    committed = subprocess.check_output(
        ['git', 'show', donors['ipc_mailbox']['commit'] + ':source_port/' + recipe], cwd=ROOT)
    if (mailbox['passed'] is not True or mailbox['source'] in native
            or mailbox['error_controls']['checks'] != 8 or mailbox['recovery_controls']['checks'] != 22
            or hashlib.sha256(committed).hexdigest() != mailbox['recipes'][recipe]
            or mailbox['preimage_sha256'] != composition.ipc_mailbox_patches.PREIMAGE):
        raise ValueError('Mailbox donor lacks independent race and native recovery evidence')
    expected_probes = {label + '-' + operation for label in ('original', 'patched')
                       for operation in ('place', 'cancel')}
    if set(mailbox['probes']) != expected_probes or any(
            (row['exit_code'] == 0) != name.startswith('patched-')
            for name, row in mailbox['probes'].items()):
        raise ValueError('Mailbox donor differential controls differ')
    original = composition.archive_sources(ROOT / 'docs/reference/SPELL2.6.10-src.zip',
                                           [mailbox['source']])[mailbox['source']]
    native[mailbox['source']] = dict(original=hashlib.sha256(original).hexdigest(),
        ported=mailbox['preimage_sha256'], patched=mailbox['patched_sha256'])
    snapshot = reports['context_snapshot']
    recipe = 'context_snapshot_patches.py'
    committed = subprocess.check_output(
        ['git', 'show', donors['context_snapshot']['commit'] + ':source_port/' + recipe], cwd=ROOT)
    if (snapshot['passed'] is not True or snapshot['source'] in native
            or snapshot['qualified_contracts'] != []
            or snapshot['passed_checks'] != {'errors':8, 'recovery':22, 'startup':40}
            or hashlib.sha256(committed).hexdigest() != snapshot['recipes'][recipe]
            or snapshot['source'] != composition.context_snapshot_patches.SOURCE
            or snapshot['original_sha256'] != composition.context_snapshot_patches.ORIGINAL
            or snapshot['preimage_sha256'] != composition.context_snapshot_patches.PORTED):
        raise ValueError('Listener snapshot donor lacks qualified source and native controls')
    probes = snapshot['probes']['probes']
    if set(probes) != {'original', 'patched'} or any(
            row['exit_code'] != (0 if name == 'patched' else 1)
            or row['observation']['coherent'] is not (name == 'patched')
            or not row['observation']['subsequent_current']
            or not row['observation']['unknown_context_rejected']
            for name, row in probes.items()):
        raise ValueError('Listener snapshot donor lacks differential interleaving controls')
    native[snapshot['source']] = dict(original=snapshot['original_sha256'],
        ported=snapshot['preimage_sha256'], patched=snapshot['patched_sha256'])
    legacy = reports['legacy_compare']
    if (legacy['passed'] is not True or legacy['qualified_contracts'] != []
            or legacy['passed_checks'] != 15 or len(legacy['retained_baseline_failures']) != 11
            or set(legacy['sources']) != set(composition.legacy_compare_patches.PREIMAGES)):
        raise ValueError('Legacy comparison donor lacks differential native evidence')
    for recipe in ('legacy_compare_patches.py', 'legacy_compare_syntax.py'):
        committed = subprocess.check_output(
            ['git', 'show', donors['legacy_compare']['commit'] + ':source_port/' + recipe], cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != legacy['recipes'][recipe]:
            raise ValueError('Legacy comparison recipe differs from its qualified donor')
    for name, row in legacy['sources'].items():
        hashes = {key.removesuffix('_sha256'): value for key, value in row.items()}
        if (hashes['original'], hashes['ported']) != composition.legacy_compare_patches.PREIMAGES[name]:
            raise ValueError('Legacy comparison donor preimage differs: ' + name)
        if name in native:
            if native[name]['original'] != hashes['original'] or native[name]['patched'] != hashes['ported']:
                raise ValueError('Legacy comparison does not follow the qualified TIME correction')
            native[name]['patched'] = hashes['patched']
        else:
            native[name] = hashes
    for key, count, recipe in (('wait_interrupt', 24, composition.wait_interrupt_patches),
                               ('proc_dictionary', 16, composition.proc_dictionary_patches)):
        report = reports[key]
        overlay = report['qualification_identity']['evidence']
        filename = key + '_patches.py'
        committed = subprocess.check_output(
            ['git', 'show', donors[key]['commit'] + ':source_port/' + filename], cwd=ROOT)
        if (report['passed'] is not True or report['qualified_contracts'] != []
                or len(report['checks']) != count + 4
                or any(row['passed'] is not True for row in report['checks'].values())
                or not overlay['passed'] or overlay['full_release_accepted']
                or hashlib.sha256(committed).hexdigest() != overlay['recipes'][filename]
                or set(overlay['sources']) != set(recipe.PREIMAGES)):
            raise ValueError('Diagnostic donor lacks complete native evidence: ' + key)
        for name, row in overlay['sources'].items():
            hashes = {label.removesuffix('_sha256'): value for label, value in row.items()}
            if (hashes['original'], hashes['ported']) != recipe.PREIMAGES[name]:
                raise ValueError('Diagnostic donor preimage differs: ' + name)
            if name in native:
                if native[name]['original'] != hashes['original'] or native[name]['patched'] != hashes['ported']:
                    raise ValueError('Diagnostic donor does not follow its qualified predecessor: ' + name)
                native[name]['patched'] = hashes['patched']
            else:
                native[name] = hashes
    prefix = '/usr/local/lib/python3.13/site-packages/'
    python = {name.removeprefix(prefix):value for name,value in reports['baseline']['runtime_sources']['installed'].items()}
    python.update({name:reports['command']['runtime_sources']['installed'][prefix+name]
                   for name in composition.cmd_patches.PREIMAGES})
    python.update({name:row['sha256'] for name,row in reports['time_verify']['python_manifest'].items()})
    for key,kind in (('resource','resource-conformance-patch'),('limit','limit-patch')):
        python.update({name:row['sha256'] for name,row in reports[key]['runtime_sources']['manifests'][kind].items()})
    python.update(reports['database']['runtime_sources']['installed'])
    python.update(reports['user_database']['runtime_sources']['installed'])
    octal = reports['database_values']
    recipe = 'source_port/database_values_patches.py'
    committed = subprocess.check_output(
        ['git','show',donors['database_values']['commit']+':'+recipe],cwd=ROOT)
    if (octal['passed'] is not True or octal['qualified_contracts'] != []
            or octal['passed_checks'] != {'values_and_import':24,'user_persistence':20,'user_prompts':2}
            or hashlib.sha256(committed).hexdigest() != octal['inputs'][recipe]):
        raise ValueError('Database value donor lacks the qualified diagnostic source identity')
    source = octal['source']
    if (set(composition.database_values_patches.PREIMAGES) != {source['name']}
            or python[source['name']] != source['preimage_sha256']
            or composition.database_values_patches.PREIMAGES[source['name']] != source['preimage_sha256']):
        raise ValueError('Database value donor differs from the qualified import/persistence chain')
    python[source['name']] = source['patched_sha256']
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
    send = reports['send_verify']['runtime_sources']['diagnostic_overlay']['overlay']['send-verify-patch']['manifest']
    for name, row in send.items():
        if python[name] != row['preimage_sha256']:
            raise ValueError('Send donor chain differs from qualified timing output: '+name)
        python[name] = row['sha256']
    for key, recipe in (('rng', 'rng_patches.py'), ('rng_state', 'rng_state_patches.py')):
        donor = reports[key]
        committed = subprocess.check_output(['git','show',donors[key]['commit']+':source_port/'+recipe],cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != donor['inputs']['source_port/'+recipe]:
            raise ValueError('Ranging recipe differs from qualified donor: '+recipe)
        for name, row in donor['runtime_sources']['overlay']['manifest'].items():
            outputs = python if name.startswith('spell/') else driver
            if name in outputs:
                if outputs[name] != row['preimage_sha256']:
                    raise ValueError('Ranging donor differs from earlier qualified output: '+name)
            elif donor['inputs'].get('driver_plugin/src/'+name) != row['preimage_sha256']:
                raise ValueError('Ranging driver input differs from qualified donor: '+name)
            outputs[name] = row['sha256']
    # These expectations come from the retained native image, independently of
    # the current composition result. Every command/display source was present
    # in that image; unchanged prior donors must still agree exactly.
    command_review = reports['display_commands']
    raw_path = Path(command_review['raw']['path'])
    raw_bytes = raw_path.read_bytes()
    if (not command_review['passed'] or len(command_review['observations']) != 19
            or hashlib.sha256(raw_bytes).hexdigest() != command_review['raw']['sha256']):
        raise ValueError('Command/display donor lacks its independently reviewed native capture')
    commands = json.loads(raw_bytes)
    if not commands['passed'] or commands['runtime_image'] != command_review['runtime_image']:
        raise ValueError('Command/display runtime differs from its native review')
    additions = (composition.display_patches, composition.command_feature_patches,
                 composition.command_catalog_patches, composition.command_group_patches)
    changed = {name for recipe in additions for name in recipe.PREIMAGES}
    installed = commands['runtime_sources']['installed']
    for recipe in additions:
        name = 'source_port/'+Path(recipe.__file__).name
        captured = subprocess.check_output(['git','show',command_review['source_revision']+':'+name],cwd=ROOT)
        if hashlib.sha256(captured).hexdigest() != commands['inputs'][name]:
            raise ValueError('Command/display donor recipe differs from its frozen source: '+name)
        if captured.replace(b'\r\n',b'\n') != (ROOT/name).read_bytes().replace(b'\r\n',b'\n'):
            raise ValueError('Current command/display recipe differs from native donor: '+name)
    for previous, names in ((python, composition.PYTHON_NAMES), (driver, composition.DRIVER_NAMES)):
        for name in names:
            if name in previous and name not in changed and previous[name] != installed[name]:
                raise ValueError('Command/display donor changes an unrelated qualified source: '+name)
            previous[name] = installed[name]
    if composition.limit_feature_patches in composition.DRIVER_RECIPES:
        from feature_source_donors import apply
        source_identities=json.loads((ROOT/'distribution/evidence/limit-telemetry-source-donors.json').read_bytes())
        donors.update(apply(python,driver,composition,source_identities))
    from library_source_donors import apply as apply_libraries
    native_distribution = apply_libraries(python,native,composition,reports)
    from ranging_source_donor import apply as apply_ranging
    driver_additions=apply_ranging(python,driver,composition,reports['ranging_complete'])
    from memory_source_donor import apply as apply_memory
    memory_additions=apply_memory(python,driver,composition,reports['memory_complete'],reports['ranging_complete'])
    assert not set(driver_additions) & set(memory_additions)
    driver_additions.update(memory_additions)
    from database_source_donor import apply as apply_database
    apply_database(python,composition,reports['database_formats'])
    from send_source_donor import apply as apply_send
    apply_send(python,composition,reports['send_complete'])
    host = {name:value for name,value in reports['child_host']['inputs'].items()
            if name.startswith('host_runtime/python/')}
    startup = reports['context_startup']
    if (not startup['passed'] or startup['qualified_contracts'] != []
            or startup['native_scheduler_checks'] != 9
            or set(startup['host_sources']) != {'host_runtime/python/native.py'}):
        raise ValueError('Context startup donor lacks independent native evidence')
    for name, value in startup['host_sources'].items():
        committed = subprocess.check_output(
            ['git', 'show', donors['context_startup']['commit'] + ':' + name], cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != value:
            raise ValueError('Context startup donor differs from its exact commit')
        host[name] = value
    console_commit = donors['console_input']['commit']
    client_names = subprocess.check_output(
        ['git','ls-tree','-r','--name-only',console_commit,'host_plugin/src'],cwd=ROOT,text=True).splitlines()
    host_client = {name:hashlib.sha256(subprocess.check_output(
        ['git','show',console_commit+':'+name],cwd=ROOT)).hexdigest()
        for name in client_names if name.endswith('.py')}
    for name,value in reports['console_input']['inputs'].items():
        if name.startswith('host_plugin/src/') and host_client.get(name) != value:
            raise ValueError('Console donor source differs from its exact commit: '+name)
    upgrade = reports['host_upgrade']
    if not upgrade['passed'] or not all(upgrade['wheel_record'][name] for name in
            ('all_members_verified','installed_members_match','source_members_match')):
        raise ValueError('Host upgrade donor lacks complete installed wheel evidence')
    upgraded_client = {'host_plugin/src/'+name:value for name,value in upgrade['host_client_sources'].items()}
    if set(upgraded_client) != set(host_client):
        raise ValueError('Host upgrade donor changes the declared client source set')
    host_package = {name:value for name,value in upgrade['inputs'].items()
                    if name in ('host_plugin/pyproject.toml','host_plugin/README.md','host_plugin/LICENSE')}
    for name,value in {**upgraded_client,**host_package}.items():
        raw = subprocess.check_output(['git','show',donors['host_upgrade']['commit']+':'+name],cwd=ROOT)
        if hashlib.sha256(raw).hexdigest() != value:
            raise ValueError('Host upgrade donor source differs from its exact commit: '+name)
    host_client = upgraded_client
    if 'final_language' in reports:
        from final_source_donors import apply_final
        apply_final(native, driver, host, host_client, reports)
    if set(native) != set(composition.NATIVE_NAMES):
        raise ValueError('Qualified native source set differs from composition')
    result = {'schema':'openbexi.spell.qualified-source-donors/1',
        'scope':'Independent tranche source expectations only; combined runtime behavior remains unqualified.',
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'donors':donors,'native':native,
        'python':{name:python[name] for name in composition.PYTHON_NAMES},'driver':driver,
        'host':host, 'host_client':host_client, 'host_package':host_package,
        'native_distribution':native_distribution,
        'driver_additions':driver_additions,
        'host_candidate':{'version':upgrade['version'],'wheel_sha256':upgrade['wheel']['sha256']},
        'full_v05_accepted':False,'full_v06_accepted':False}
    output = ROOT/'distribution/evidence/followup-qualified-sources.json'
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'output':str(output),'native':len(native),'python':len(result['python']),'driver':len(driver)},indent=2))


if __name__ == '__main__':
    main()
