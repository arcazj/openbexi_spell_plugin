"""Adopt only independently reviewed final prompt, host and RPC successors."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'conformance'))
digest = lambda data: hashlib.sha256(data).hexdigest()


def exact(reference):
    data = Path(reference['path']).read_bytes()
    assert digest(data) == reference['sha256']
    return json.loads(data)


def committed(revision, name):
    return subprocess.check_output(['git', 'show', revision+':'+name], cwd=ROOT)


def apply(native, driver, host, host_client, composition, reports, donors):
    prompt = reports['prompt_complete']
    assert prompt['passed'] is True
    baseline = prompt['baseline']
    encoded = committed(baseline['commit'], baseline['path'])
    assert digest(encoded) == baseline['sha256']
    previous = json.loads(encoded)
    assert native == previous['native'] and driver == previous['driver']
    assert host == previous['host'] and host_client == previous['host_client']
    assert set(prompt['native_changes']) == set(composition.prompt_complete_patches.PREIMAGES)
    assert set(prompt['driver_changes']) == set(composition.event_text_patches.PREIMAGES)
    assert set(prompt['independent_reviews']) == {'prompt', 'child', 'event'}
    for kind, count in (('prompt', 12), ('child', 4), ('event', 8)):
        review = exact(prompt['independent_reviews'][kind])
        assert review['passed'] is True and review['runtime_image'] == prompt['runtime_image']
        assert len(review['checks']) == count and all(row['passed'] for row in review['checks'].values())
    for recipe, expected in prompt['recipes'].items():
        name = 'source_port/'+recipe
        assert digest(committed(donors['prompt_complete']['commit'], name)) == expected
        assert digest((ROOT/name).read_bytes()) == expected
    for name, change in prompt['native_changes'].items():
        assert change['before_sha256'] == composition.prompt_complete_patches.PREIMAGES[name]
        if name in native:
            assert native[name]['patched'] == change['before_sha256']
            assert all(native[name][key] == change['source'][key] for key in ('original', 'ported'))
        else:
            assert name == composition.prompt_complete_patches.HEADER
            assert change['source']['original'] == change['source']['ported'] == change['before_sha256']
        assert change['source']['patched'] == change['after_sha256']
        native[name] = dict(change['source'])
    assert native == prompt['native']
    for name, change in prompt['driver_changes'].items():
        assert driver[name] == change['before_sha256'] == composition.event_text_patches.PREIMAGES[name]
        driver[name] = change['after_sha256']
    assert driver == prompt['driver']

    # Native DAP captures cover the host changes. Client reminder dispatch is
    # separately tested against these exact committed sources; installation
    # and platform qualification remain v0.6 work.
    host_changes = {'host_runtime/python/'+name for name in ('adapter.py', 'children.py', 'prompts.py')}
    client_changes = {'host_plugin/src/openbexi_spell_host/'+name for name in ('dap.py', 'runner.py')}
    added = {'host_plugin/src/openbexi_spell_host/sound.py'}
    assert set(host) == set(prompt['host'])
    assert {name for name in host if host[name] != prompt['host'][name]} == host_changes
    assert set(prompt['host_client']) == set(host_client) | added
    assert {name for name in host_client if host_client[name] != prompt['host_client'][name]} == client_changes
    validation = prompt['host_client_validation']
    xml = Path(validation['junit']['path']).read_bytes()
    assert digest(xml) == validation['junit']['sha256']
    suites = ET.fromstring(xml).findall('.//testsuite')
    assert suites and sum(int(s.get('tests', 0)) for s in suites) >= 63
    assert all(int(s.get(key, 0)) == 0 for s in suites for key in ('failures', 'errors', 'skipped'))
    for group in ('host', 'host_client'):
        for name, expected in prompt[group].items():
            assert digest(committed(validation['source_commit'], name)) == expected
            assert digest((ROOT/name).read_bytes()) == expected
    host.update(prompt['host']); host_client.update(prompt['host_client'])

    command = reports['memory_command']
    assert command['passed'] is True
    assert set(command['independent_reviews']) == {'group', 'memory'}
    for kind, count, key in (('group', 19, 'observations'), ('memory', 32, 'checks')):
        review = exact(command['independent_reviews'][kind])
        assert review['passed'] is True and review['runtime_image'] == command['runtime_image']
        assert len(review[key]) == count
        if key == 'checks': assert all(row['passed'] for row in review[key].values())
    recipe = composition.memory_command_results_patches
    assert command['source'] == recipe.SOURCE
    assert driver[recipe.SOURCE] == command['before_sha256'] == recipe.PREIMAGES[recipe.SOURCE]
    name = 'source_port/memory_command_results_patches.py'
    assert digest(committed(donors['memory_command']['commit'], name)) == command['recipe']['sha256']
    assert digest((ROOT/name).read_bytes()) == command['recipe']['sha256']
    from limit_telemetry_sources import wheel_sources
    before = wheel_sources(Path(command['baseline_driver_wheel']['path']))
    after = wheel_sources(Path(command['driver_wheel']['path']))
    assert digest(Path(command['baseline_driver_wheel']['path']).read_bytes()) == command['baseline_driver_wheel']['sha256']
    assert digest(Path(command['driver_wheel']['path']).read_bytes()) == command['driver_wheel']['sha256']
    assert digest(before[recipe.SOURCE]) == command['before_sha256']
    assert recipe.apply(recipe.SOURCE, before[recipe.SOURCE]) == after[recipe.SOURCE]
    assert digest(after[recipe.SOURCE]) == command['after_sha256']
    driver[recipe.SOURCE] = command['after_sha256']
    assert all(digest(after[name]) == expected for name, expected in driver.items())
    return validation
