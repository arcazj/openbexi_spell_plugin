"""Refresh an existing coverage checkpoint only after all native suites pass."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from run_language_regressions import ROOT, SUITES, sha, validate_report


def reference(record):
    path = Path(record['path'])
    if sha(path) != record['sha256']:
        raise ValueError('Retained evidence changed: ' + str(path))
    return str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, action='append', required=True)
    parser.add_argument('--baseline-commit', required=True)
    parser.add_argument('--native-gate-dir', type=Path, required=True)
    parser.add_argument('--prompt-controls', type=Path, required=True)
    parser.add_argument('--rng-driver', type=Path, required=True)
    parser.add_argument('--rng-legacy-and-migration', type=Path, required=True)
    parser.add_argument('--rng-baseline', type=Path, required=True)
    parser.add_argument('--rng-state-baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    baseline = subprocess.check_output(['git', 'rev-parse', args.baseline_commit],
                                       cwd=ROOT, text=True).strip()
    def old(name):
        return json.loads(subprocess.check_output(
            ['git', 'show', baseline + ':conformance/evidence/' + name + '.json'], cwd=ROOT))

    raw, sessions, image = {}, [], None
    minima = {row[0]: row[3] for row in SUITES}
    for path in args.session:
        session = json.loads(path.read_bytes())
        if image is not None and session['image'] != image:
            raise ValueError('Sessions use different runtimes')
        image = session['image']
        sessions.append({'path': str(path.resolve()), 'sha256': sha(path)})
        for stage in session['suites']:
            if not stage['passed']:
                continue  # Retain failed attempts; only explicit passing reruns qualify.
            name = stage['suite']
            if name in raw:
                raise ValueError('Select a single passing report per suite: ' + name)
            if stage['exit_code'] != 0:
                raise ValueError('Passing stage has a failed process')
            reference(stage['log'])
            raw[name] = reference(stage['raw'])
            validate_report(Path(raw[name]), image, minima[name])
    if set(raw) != set(minima):
        raise ValueError('Incomplete native sequence: ' + ', '.join(sorted(set(minima) - set(raw))))

    # The combined runtime previously passed builds but failed answer ordering
    # and prompt abort. Require the independent controls before refreshing rows.
    sys.path.insert(0, str(ROOT / 'conformance'))
    from prompt_control_report import qualify as qualify_controls
    controls = json.loads(args.prompt_controls.read_bytes())
    proofs = {name: Path(reference(row)) for name, row in controls['raw'].items()}
    verified = qualify_controls(proofs['stress'], proofs['modes'], proofs['timed'],
                                proofs['native_pair'], proofs['abort_stress'])
    if controls != verified or controls['runtime_image'] != image:
        raise ValueError('Prompt controls differ from the selected runtime or current evidence')

    commands = []
    def run(script, *options):
        command = [sys.executable, '-X', 'utf8', str(ROOT / 'conformance' / script),
                   *map(str, options)]
        subprocess.run(command, cwd=ROOT, check=True)
        commands.append(command)

    direct = {'data': 'data', 'files': 'files', 'data-race': 'data-race', 'flow': 'flow',
              'common-silence': 'common-silence', 'dta': 'dta', 'ui': 'ui',
              'dta-ipc': 'dta-ipc', 'time': 'time', 'python': 'python', 'common': 'common'}
    for suite, target in direct.items():
        # Canonical reports must retain the bytes whose hashes Git will publish.
        # Preserve immutable raw evidence separately, including its line endings.
        (ROOT / 'conformance/evidence' / (target + '.json')).write_text(
            Path(raw[suite]).read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
    for suite, script in [('obs', 'obs'), ('cmd', 'cmd'), ('events', 'events'),
                          ('scheduler', 'scheduler'), ('value-units', 'value_units'),
                          ('timing', 'timing'), ('send-verify', 'send_verify'), ('resource', 'resource')]:
        run(script + '_report.py', raw[suite])
    counterexamples = old('limit')['counterexamples']
    run('limit_report.py', raw['limit'], raw['obs'],
        '--baseline', reference(counterexamples[0]),
        '--numeric_failure', reference(counterexamples[1]),
        '--range_failure', reference(counterexamples[2]),
        *[item for row in old('limit').get('retained_qualification_failures', [])
          for item in ('--retained_failure', reference(row))])
    run('notification_report.py', '--result', raw['notification'],
        '--baseline', reference(old('notification')['baseline']))
    for suite, report in [('database-import', 'database_import'), ('user-database', 'user_database')]:
        run(report + '_report.py', raw[suite], '--baseline', reference(old(report)['baseline']),
            '--files', raw['files'], '--data', raw['data'])
    scdb = old('scdb')
    run('scdb_report.py', raw['scdb'], '--baseline', reference(scdb['baseline']),
        '--database-import', raw['database-import'],
        '--checkpoint-gap', reference(scdb['retained_observations']['checkpoint_lambda_error']),
        '--policy-oracle-correction', reference(scdb['retained_observations']['save_failure_policy_oracle']))
    checkpoint = old('checkpoint_error')['evidence']
    options = [item for name in ('baseline', 'audit', 'ipc_baseline', 'ipc_blocker')
               for item in ('--' + name.replace('_', '-'), reference(checkpoint[name]))]
    run('checkpoint_error_report.py', *options, '--candidate', raw['checkpoint'],
        '--expanded', raw['checkpoint-expanded'], '--ipc-candidate', raw['checkpoint-ipc'],
        '--integrated-gate-dir', args.native_gate_dir,
        '--output', ROOT / 'conformance/evidence/checkpoint_error.json')
    identity = old('checkpoint_identity')
    run('checkpoint_identity_report.py',
        '--baseline-source', reference(identity['baseline_source']['evidence']),
        '--baseline-context', reference(identity['baseline_context']['evidence']),
        '--errors', raw['identity-errors'], '--recovery', raw['identity-recovery'],
        '--integrated-gate-dir', args.native_gate_dir,
        '--output', ROOT / 'conformance/evidence/checkpoint_identity.json')
    run('prompt_timeout_report.py', raw['prompt-timeout'],
        '--native-pair', args.native_gate_dir.resolve().parents[1] / 'result.json')
    run('child_arguments_report.py', raw['child-arguments'])
    run('predefined_containers_report.py', '--dta', raw['dta'], '--ipc', raw['dta-ipc'],
        '--child', raw['child-arguments'], '--image', image)
    run('child_start_report.py', raw['child-start'], '--image', image)
    run('child_return_report.py', '--start', raw['child-start'],
        '--modes', proofs['modes'], '--image', image)
    run('child_execution_report.py', '--start', raw['child-start'],
        '--modes', proofs['modes'], '--image', image)
    run('database_scope_report.py', raw['database-import'], '--image', image)
    run('database_values_composed_report.py', '--values', raw['database-values'],
        '--user', raw['user-database'], '--image', image)
    run('legacy_compare_composed_report.py', raw['legacy-compare'], '--image', image)
    run('context_snapshot_composed_report.py', raw['context-startup'], '--image', image)
    run('prompt_startup_composed_report.py', raw['prompt-startup'], '--image', image)
    run('python_sections_report.py', '--python', raw['python'], '--comparison', raw['legacy-compare'],
        '--database', raw['database-import'], '--values', raw['database-values'],
        '--user', raw['user-database'], '--image', image)
    run('child_policy_report.py', '--policy', raw['child-policy'], '--start', raw['child-start'],
        '--modes', proofs['modes'], '--image', image)
    run('wait_time_report.py', raw['wait-time'], '--image', image)
    run('wait_control_report.py', raw['wait-controls'], '--image', image)
    run('wait_interval_report.py', raw['wait-intervals'], '--image', image)
    run('proc_dictionary_composed_report.py', '--baseline', raw['proc-metadata'],
        '--lifecycle', raw['proc-lifecycle'], '--image', image)
    run('rng_report.py', raw['rng-catalog'], '--baseline', args.rng_baseline)
    run('rng_state_report.py', raw['rng-state'], '--baseline', args.rng_state_baseline,
        '--driver', args.rng_driver, '--legacy-and-migration', args.rng_legacy_and_migration)

    # A checkpoint after the command/display promotion includes these fifty
    # requirements. Refresh their actual source/artifact review before checking
    # that every previously qualified row still passes on this runtime.
    revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    run('command_routing_review.py','--raw',raw['cmd'],'--image',image,'--revision',revision)
    run('command_display_composed_report.py',
        '--scheduling',raw['command-scheduling'],'--catalog',raw['command-catalog'],
        '--group',raw['command-group'],'--display',raw['gcs-display'],
        '--image',image,'--revision',revision)

    sys.path.insert(0, str(ROOT / 'conformance'))
    from check import supported_check, validate
    coverage = json.loads(subprocess.check_output(
        ['git', 'show', baseline + ':conformance/coverage.json'], cwd=ROOT))
    reports = {}
    for row in coverage['rows']:
        if row['status'] != 'QUALIFIED':
            continue
        for dimension, binding in row['evidence'].items():
            path = ROOT / binding['report']
            if path not in reports:
                reports[path] = (json.loads(path.read_bytes()), sha(path))
            report, digest = reports[path]
            if (report.get('runtime_image') != image
                    or not supported_check(report, binding['check'], dimension)
                    or row['id'] not in report['checks'][binding['check']]['contracts']):
                raise ValueError('Existing qualified contract regressed: ' + row['id'])
            binding['sha256'] = digest
    inventory = json.loads((ROOT / 'conformance/inventory.json').read_bytes())
    gate = validate(inventory, coverage, ROOT)
    (ROOT / 'conformance/coverage.json').write_text(json.dumps(coverage, indent=2) + '\n',
                                                  encoding='utf-8', newline='\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {'passed': True, 'scope': 'Existing conformance coverage requalified on the combined runtime',
              'runtime_image': image, 'baseline_commit': baseline, 'sessions': sessions,
              'raw_reports': {k: {'path': v, 'sha256': sha(Path(v))} for k, v in raw.items()},
              'qualifier_commands': commands, 'counts': gate['counts'], 'total': gate['total'],
              'coverage_sha256': sha(ROOT / 'conformance/coverage.json'),
              'prompt_controls': {'path': str(args.prompt_controls.resolve()),
                                  'sha256': sha(args.prompt_controls)},
              'full_v05_accepted': gate['accepted'], 'full_v06_accepted': False}
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': str(args.output), 'counts': gate['counts']}))


if __name__ == '__main__':
    main()
