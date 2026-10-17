"""Qualify display and command candidates on freshly composed installed wheels."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'conformance'), str(ROOT/'distribution')]
import command_features_report as commands
import command_group_review as groups
import display_report as displays
import command_routing_review as routing
from installed_provenance import verify_stages
from driver_composition_review import verify_driver_stages

sha, read, ref = commands.sha, commands.read, commands.ref


def qualify(paths, image, revision):
    assert set(paths) == {'scheduling', 'catalog', 'group', 'display'}
    command_donor = commands.qualify(read(ROOT/'conformance/evidence/command_feature_inputs.json'))
    display_record = read(ROOT/'conformance/evidence/display.json')
    display_donor = displays.qualify(Path(display_record['raw']['path']), Path(display_record['baseline']['path']),
        display_record['runtime_image'], Path(display_record['overlay_manifest']['path']).parent,
        display_record['baseline_revision'], display_record['source_revision'])
    assert command_donor['passed'] and display_donor['passed']
    inputs, checks, raw, artifacts = {}, {}, {}, {}
    runtime = None
    for kind, path in paths.items():
        if kind in ('scheduling', 'catalog'):
            report, leaves = commands.verify_cases(path, image, revision, kind)
        elif kind == 'display':
            report, leaves = displays.verify_cases(path, image, revision)
        else:
            groups.review(path, None, revision, image, composed=True)
            report = read(path)
            leaves = {name: dict(deepcopy(row), contracts=[],
                oracle='Native Group/Block statuses, independent TCP packets and immutable member receipts')
                for name,row in report['checks'].items()}
        assert report['composed'] and report['runtime_sources']['profile'] == 'fresh-composed-display-command-wheel/1'
        if runtime is None:runtime = report['runtime_sources']
        assert report['runtime_sources'] == runtime
        assert not set(checks) & set(leaves)
        for name, value in report['inputs'].items():
            assert sha(ROOT/name) == value
            if name in inputs:assert inputs[name] == value
            inputs[name] = value
        workspace = path.parent/'workspace'
        actual = {p.relative_to(workspace).as_posix(): sha(p) for p in workspace.rglob('*') if p.is_file()}
        assert report['artifacts'] == actual
        artifacts[kind] = actual
        checks.update(leaves)
        raw[kind] = ref(path)
    integrated = runtime['integrated']
    native = integrated['manifest']['composition']['native']
    python = integrated['manifest']['composition']['python']
    driver = integrated['driver_composition']['manifest']
    assert native['recipes'] == python['recipes'] == driver['recipes']
    for kind, record in (('native', native), ('python', python)):
        verify_stages(kind, record)
    verify_driver_stages(driver)
    for name, value in integrated['native_artifacts'].items():
        assert runtime['installed']['spell_native/bin/'+name] == value
    for name, value in integrated['python_sources'].items():
        assert runtime['installed'][name] == value
    for name, value in driver['python_sources'].items():
        assert runtime['installed'][name] == value
    # Compare source bodies with the independently observed final diagnostic
    # image. Native binaries change with the composed checkpoint identity and
    # are separately accepted by the two clean rebuilds.
    golden = read(Path(command_donor['manifest']['group']['path']))['runtime_sources']['installed']
    def application_source(name):
        return name.startswith(('spell/', 'spell_native/', 'openbexi_spell_dss/', 'openbexi_dss_proxy/')) and '/_composition/' not in name and '/provenance/' not in name
    expected_names = {n for n in golden if application_source(n)}
    selected = {name: value for name,value in golden.items()
        if name.endswith('.py') and application_source(name)}
    correction = read(ROOT/'conformance/evidence/command_routing_validation.json')
    assert correction == routing.review(Path(correction['candidate']['path']), image, revision)
    corrected = correction['source'].removeprefix('driver_plugin/src/')
    assert selected[corrected] == correction['before_sha256']
    selected[corrected] = correction['after_sha256']
    source_extension = None
    if 'memory_ranging_patches.py' in driver['recipes']:
        # These final bodies were independently replayed from the memory,
        # ranging, database, Send, telemetry, limit and library donor reviews.
        revision_id = '70a4d1abeeb708a538aeb10d3e04637f4f24afff'
        name = 'distribution/evidence/followup-qualified-sources.json'
        encoded = subprocess.check_output(['git','show',revision_id+':'+name],cwd=ROOT)
        expected = json.loads(encoded)
        assert read(ROOT/name) == expected
        assert expected['generator_sha256'] == sha(ROOT/'distribution/record_qualified_sources.py')
        assert {key:value['patched_sha256'] for key,value in python['sources'].items()} == expected['python']
        for key,value in expected['native'].items():
            assert native['sources'][key] == {label+'_sha256':digest for label,digest in value.items()}
        for key,value in expected['driver'].items():assert driver['python_sources'][key] == value
        selected.update(expected['python']); selected.update(expected['driver'])
        selected.update(expected['driver_additions'])
        modules={'spell_native/'+Path(key).name:value for key,value in expected['native_distribution'].items()}
        selected.update(modules)
        expected_names.update(expected['driver_additions']); expected_names.update(modules)
        source_extension = dict(commit=revision_id, path=name, sha256=commands.sha(ROOT/name))
    assert {n for n in runtime['installed'] if application_source(n)} == expected_names
    for name, value in selected.items():
        assert runtime['installed'][name] == value, name
    recipes = ('display_patches.py', 'command_feature_patches.py', 'command_catalog_patches.py', 'command_group_patches.py')
    for recipe in recipes:
        expected = read(Path(command_donor['manifest']['group']['path']))['inputs']['source_port/'+recipe]
        assert native['recipes'][recipe]['sha256'] == expected
    candidates = []
    for donor in (command_donor, display_donor):
        for contract in donor['candidate_contracts']:
            assert contract not in candidates
            candidates.append(contract)
            for dimension in commands.DIMENSIONS:
                key = contract+':'+dimension
                item = deepcopy(donor['checks'][key])
                assert all(checks[name]['passed'] and checks[name]['dimension'] == dimension for name in item['dependencies'])
                assert all(checks[name]['passed'] and checks[name]['dimension'] == 'encoding' for name in item['encoding_checks'])
                checks[key] = item
    for name in ('conformance/command_display_composed_report.py', 'conformance/command_features_report.py',
                 'conformance/command_group_review.py', 'conformance/display_report.py',
                 'tests/test_command_display_composed_report.py',
                 'conformance/command_routing_review.py', 'conformance/driver_composition_review.py', 'conformance/evidence/command_routing_validation.json',
                 'tests/test_command_routing_review.py',
                 'conformance/evidence/command_feature_inputs.json', 'distribution/run_language_regressions.py'):
        inputs[name] = sha(ROOT/name)
    return dict(passed=True, runtime_image=image, source_revision=revision, inputs=inputs,
        checks=checks, qualified_contracts=candidates, raw=raw, artifacts=artifacts,
        runtime_sources=runtime, diagnostic_sources=selected,
        routing_validation=correction, source_extension=source_extension,
        scope='26 command and 24 virtual display requirements on newly composed native and driver wheels',
        exclusions=command_donor['exclusions']+display_donor['exclusions'],
        full_v05_accepted=False, full_v06_accepted=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for kind in ('scheduling', 'catalog', 'group', 'display'):
        parser.add_argument('--'+kind, type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'conformance/evidence/command_display_composed.json')
    args = parser.parse_args()
    result = qualify({kind: getattr(args, kind) for kind in ('scheduling', 'catalog', 'group', 'display')}, args.image, args.revision)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, contracts=len(result['qualified_contracts']), output=str(args.output))))
