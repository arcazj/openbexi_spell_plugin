"""Replay final source successors only after their installed native reviews pass."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'conformance'), str(ROOT/'source_port'), str(ROOT/'driver_plugin/src')]
from limit_telemetry_sources import wheel_sources
from run_language_regressions import validate_report
import integrated_patches as composition

BASELINE = '7d50a6393413595293b27384db9506cd4cd2efef'
BASE_PATH = 'distribution/evidence/followup-qualified-sources.json'
NATIVE_RECIPES = ('prompt_complete_patches', 'prompt_empty_option_patches', 'event_empty_native_patches')
DRIVER_RECIPES = ('event_text_patches', 'memory_command_results_patches')
COUNTS = {'prompt': 12, 'child': 4, 'event': 8, 'command-group': 19, 'memory': 32, 'driver-extension': 4}
digest = lambda data: hashlib.sha256(data).hexdigest()
sha = lambda path: digest(path.read_bytes())
ref = lambda path: dict(path=str(path.resolve()), sha256=sha(path))
read = lambda path: json.loads(path.read_bytes())


def exact(reference):
    path = Path(reference['path'])
    assert sha(path) == reference['sha256'], str(path)
    return path


def committed(revision, name):
    return subprocess.check_output(['git', 'show', revision+':'+name], cwd=ROOT)


def replay(baseline, old_native, old_driver, native, driver):
    manifest = json.loads(native['spell_native/manifest.json'])
    final = manifest['composition']['native']
    native_sources = {name: dict(row) for name, row in baseline['native'].items()}
    state = {}
    prefix = 'spell_native/provenance/integrated-native/'
    for name, row in native_sources.items():
        state[name] = old_native[prefix+'patched/'+name]
        assert digest(state[name]) == row['patched']
    changes = []
    for recipe_name in NATIVE_RECIPES:
        recipe = getattr(composition, recipe_name)
        for name, before_hash in recipe.PREIMAGES.items():
            if name not in state:
                state[name] = native[prefix+'ported/'+name]
                original = digest(native[prefix+'original/'+name])
                ported = digest(state[name])
                native_sources[name] = dict(original=original, ported=ported, patched=ported)
            before = state[name]
            assert digest(before) == before_hash
            after = recipe.apply(name, before)
            stage = dict(before_sha256=before_hash, after_sha256=digest(after))
            assert [s['sources'][name] for s in final['stages']
                    if s['recipe'] == recipe_name+'.py' and name in s['sources']] == [stage]
            changes.append(dict(recipe=recipe_name+'.py', source=name, **stage))
            state[name] = after
            native_sources[name]['patched'] = digest(after)
    assert set(native_sources) == set(final['sources']) == set(composition.NATIVE_NAMES)
    for name, row in native_sources.items():
        assert final['sources'][name] == {key+'_sha256': value for key, value in row.items()}
        assert native[prefix+'patched/'+name] == state[name]
    driver_sources = dict(baseline['driver'])
    driver_state = {name: old_driver[name] for name in driver_sources}
    assert all(digest(driver_state[name]) == expected for name, expected in driver_sources.items())
    driver_changes = []
    for recipe_name in DRIVER_RECIPES:
        recipe = getattr(composition, recipe_name)
        for name, before_hash in recipe.PREIMAGES.items():
            assert digest(driver_state[name]) == before_hash
            driver_state[name] = recipe.apply(name, driver_state[name])
            driver_sources[name] = digest(driver_state[name])
            driver_changes.append(dict(recipe=recipe_name+'.py', source=name,
                before_sha256=before_hash, after_sha256=driver_sources[name]))
    assert set(driver_sources) == set(composition.DRIVER_NAMES)
    for name, expected in driver_sources.items():
        assert driver[name] == driver_state[name] and digest(driver[name]) == expected
    for name, expected in baseline['driver_additions'].items():
        assert digest(driver[name]) == expected
    for name, expected in baseline['python'].items():
        assert digest(native[name]) == expected
    return dict(native=native_sources, driver=driver_sources,
        native_changes=changes, driver_changes=driver_changes)


def qualify(candidate_path, baseline_native, baseline_driver, host_junit, source_commit):
    candidate = read(candidate_path)
    assert candidate['passed'] is True and candidate['state'] == 'completed'
    image = candidate['runtime_image']
    pair_path = exact(candidate['native_pair']); pair = read(pair_path)
    driver_path = exact(candidate['driver_pair']); driver_pair = read(driver_path)
    images_path = exact(candidate['fresh_images']); images = read(images_path)
    native_wheel = exact(candidate['native_wheel']); driver_wheel = exact(candidate['driver_wheel'])
    assert pair['passed'] and all(pair['checks'].values()) and driver_pair['passed'] and images['passed']
    assert pair['packages'][0]['sha256'] == pair['packages'][1]['sha256'] == sha(native_wheel) == images['native_wheel']['sha256']
    assert driver_pair['wheels'][0]['sha256'] == driver_pair['wheels'][1]['sha256'] == sha(driver_wheel) == images['driver_wheel']['sha256']
    assert images['driver_plugin']['image'] == image
    assert set(candidate['independent_reviews']) == set(COUNTS)
    for name, count in COUNTS.items():
        stage = candidate['stages'][name]
        assert stage['passed'] and stage['exit_code'] == 0
        exact(stage['log']); raw_path = exact(stage['raw'])
        validate_report(raw_path, image, count, root=ROOT)
        review = read(exact(candidate['independent_reviews'][name]))
        assert review['passed'] is True and review['runtime_image'] == image
        key = 'observations' if name == 'command-group' else 'checks'
        assert len(review[key]) == count
        if key == 'checks': assert all(row['passed'] is True for row in review[key].values())
        assert exact(review['raw']) == raw_path
    frozen = committed(BASELINE, BASE_PATH); baseline = json.loads(frozen)
    native = wheel_sources(native_wheel); driver = wheel_sources(driver_wheel)
    results = replay(baseline, wheel_sources(baseline_native), wheel_sources(baseline_driver), native, driver)
    recipes = {name+'.py': sha(ROOT/'source_port'/(name+'.py')) for name in (*NATIVE_RECIPES, *DRIVER_RECIPES)}
    for name, expected in recipes.items():
        assert digest(committed(source_commit, 'source_port/'+name)) == expected
        assert json.loads(native['spell_native/manifest.json'])['composition']['native']['recipes'][name]['sha256'] == expected
    host = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT/'host_runtime/python').glob('*.py')}
    client = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT/'host_plugin/src').rglob('*.py')}
    assert set(host) == set(baseline['host'])
    assert {n for n in host if host[n] != baseline['host'][n]} == {'host_runtime/python/'+n for n in ('adapter.py', 'children.py', 'prompts.py')}
    assert set(client) == set(baseline['host_client']) | {'host_plugin/src/openbexi_spell_host/sound.py'}
    assert {n for n in baseline['host_client'] if client[n] != baseline['host_client'][n]} == {'host_plugin/src/openbexi_spell_host/'+n for n in ('dap.py', 'runner.py')}
    for name, expected in {**host, **client}.items():
        assert digest(committed(source_commit, name)) == expected
    xml = ET.fromstring(host_junit.read_bytes()); suites = xml.findall('.//testsuite')
    assert suites and sum(int(s.get('tests', 0)) for s in suites) >= 78
    assert all(int(s.get(key, 0)) == 0 for s in suites for key in ('failures', 'errors', 'skipped'))
    sound = {case.get('name') for case in xml.findall('.//testcase') if case.get('classname') == 'host_plugin.tests.test_prompt_sound'}
    assert sound == {'test_windows_reminder_uses_host_audio', 'test_terminal_fallback_keeps_session_available[linux]',
        'test_terminal_fallback_keeps_session_available[win32]', 'test_dap_relay_sounds_and_forwards_same_prompt_notification'}
    bridge = read(exact(candidate['bridge']))
    assert {'DefaultProvided', 'TimeoutMicroseconds'} <= set(bridge['fields'])
    snapshot = images_path.parent/'source'
    bridge_inputs = {name: sha(ROOT/name) for name in ('host_runtime/build_bridge.py', 'host_runtime/native_bridge.cpp')}
    for name, expected in bridge_inputs.items():
        assert sha(snapshot/name) == digest(committed(source_commit, name)) == expected
    return dict(passed=True, runtime_image=image, source_commit=source_commit,
        baseline=dict(commit=BASELINE, path=BASE_PATH, sha256=digest(frozen),
            native_wheel=ref(baseline_native), driver_wheel=ref(baseline_driver)),
        candidate=ref(candidate_path), native_pair=ref(pair_path), driver_pair=ref(driver_path),
        fresh_images=ref(images_path), native_wheel=ref(native_wheel), driver_wheel=ref(driver_wheel),
        recipes=recipes, independent_reviews=candidate['independent_reviews'], host=host, host_client=client,
        host_client_validation=dict(source_commit=source_commit, junit=ref(host_junit)),
        bridge_inputs=bridge_inputs, bridge=ref(exact(candidate['bridge'])), **results,
        full_v05_accepted=False, scope='Independently replayed final source successors and installed native behavior; full language sequence still required.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'baseline-native', 'baseline-driver', 'host-junit', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    result = qualify(args.candidate.resolve(), args.baseline_native.resolve(), args.baseline_driver.resolve(), args.host_junit.resolve(), args.source_commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(args.output), passed=True, native=len(result['native']), driver=len(result['driver']))))
