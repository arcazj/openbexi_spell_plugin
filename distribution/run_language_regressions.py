"""Run the full native regression sequence, retaining and checking each raw report."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid
from evidence_sources import source_bytes

ROOT = Path(__file__).resolve().parents[1]
SUITES = [
    ('context-startup', 'run_context_snapshot.py', ['--repeat', '40'], 40),
    ('prompt-startup', 'run_prompt_startup.py', ['--suite', 'early', '--composed'], 40),
    ('data', 'run_data_files.py', ['data'], 24),
    ('files', 'run_data_files.py', ['files'], 36),
    ('data-race', 'run_data_race.py', [], 4),
    ('flow', 'run_flow.py', [], 36),
    ('common-silence', 'run_silence.py', [], 4),
    ('resource', 'run_resource.py', [], 12),
    ('database-import', 'run_database_import.py', [], 16),
    ('database-values', 'run_database_values.py', [], 24),
    ('user-database', 'run_user_database.py', [], 20),
    ('dta', 'run_dta.py', [], 68),
    ('ui', 'run_ui.py', [], 62),
    ('prompt-timeout', 'run_prompt_timeout.py', [], 10),
    ('child-arguments', 'run_child_arguments.py', [], 10),
    ('child-start', 'run_child_start.py', [], 8),
    ('child-policy', 'run_child_policy.py', [], 8),
    ('rng-catalog', 'run_rng.py', ['--catalog-only'], 8),
    ('rng-state', 'run_rng_state.py', [], 21),
    ('dta-ipc', 'run_dta_edit.py', [], 64),
    ('time', 'run_native.py', [], 168),
    ('limit', 'limit_run.py', [], 79),
    ('limit-features', 'run_limit_features.py', [], 64),
    ('telemetry-features', 'run_telemetry_features.py', [], 32),
    ('notification', 'notification_run.py', [], 16),
    ('obs', 'run_obs.py', [], 189),
    ('cmd', 'run_cmd.py', [], 54),
    ('command-scheduling', 'run_command_scheduling.py', ['--composed'], 30),
    ('command-catalog', 'run_command_catalog.py', ['--composed'], 11),
    ('command-group', 'run_command_group.py', ['--composed'], 19),
    ('gcs-display', 'run_display.py', ['--composed'], 35),
    ('python', 'run_python.py', [], 488),
    ('legacy-compare', 'run_legacy_compare.py', [], 15),
    ('common', 'run_common.py', [], 44),
    ('events', 'run_events.py', [], 8),
    ('scheduler', 'run_scheduler.py', [], 9),
    ('wait-time', 'run_wait_time.py', [], 8),
    ('wait-controls', 'run_wait_control.py', [], 24),
    ('wait-intervals', 'run_wait_interval.py', [], 8),
    ('proc-metadata', 'run_proc_metadata.py', [], 4),
    ('proc-lifecycle', 'run_proc_lifecycle.py', [], 12),
    ('value-units', 'run_value_units.py', [], 38),
    ('scdb', 'scdb_run.py', [], 26),
    ('timing', 'run_timing.py', [], 36),
    ('send-verify', 'run_send_verify.py', [], 18),
    ('checkpoint', 'checkpoint_error_run.py', [], 24),
    ('checkpoint-expanded', 'checkpoint_error_run.py',
     [part for case in ('nested-unwind', 'finally-unwind', 'replace-error',
                       'recursive-unwind', 'repeated-catch') for part in ('--case', case)], 20),
    ('checkpoint-ipc', 'checkpoint_error_run.py', ['--ipc', '--mode', 'DISABLED'], 4),
    ('identity-errors', 'checkpoint_identity_run.py', [], 8),
    ('identity-recovery', 'checkpoint_identity_run.py', ['--recovery'], 22),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_report(path, image, minimum, root=ROOT, source_revision=None):
    report = json.loads(path.read_bytes())
    if report.get('runtime_image') != image:
        raise ValueError('Raw report image differs from selected runtime')
    checks = report.get('checks')
    if not isinstance(checks, dict) or len(checks) < minimum:
        raise ValueError('Missing required raw checks')
    failed = [name for name, row in checks.items() if row.get('passed') is not True]
    if failed or report.get('passed') is False or report.get('controller_exit_code', 0) != 0:
        raise ValueError('Raw report failed: ' + ', '.join(failed))
    inputs = report.get('inputs')
    if not inputs:
        raise ValueError('Raw report lacks source bindings')
    for name, expected in inputs.items():
        if hashlib.sha256(source_bytes(root, name, source_revision)).hexdigest() != expected:
            raise ValueError('Raw report source changed: ' + name)
    return {'path': str(path), 'sha256': sha(path), 'checks': len(checks),
            'source_inputs_verified': len(inputs)}


def report_from_stdout(stdout):
    decoder = json.JSONDecoder()
    for offset, character in enumerate(stdout):
        if character != '{':
            continue
        try:
            item, _ = decoder.raw_decode(stdout[offset:])
        except ValueError:
            continue
        if isinstance(item, dict) and isinstance(item.get('evidence', item.get('output')), str):
            return Path(item.get('evidence', item.get('output'))) / 'result.json'
    raise ValueError('Runner did not identify its raw report')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / '.qualification/language-regressions')
    parser.add_argument('--suite', action='append', choices=[s[0] for s in SUITES])
    args = parser.parse_args()
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image,
                                     '--format', '{{.Id}}'], text=True).strip()
    output = args.output.resolve() / uuid.uuid4().hex
    output.mkdir(parents=True)
    result = {'passed': False, 'state': 'running', 'complete_sequence': args.suite is None,
              'image': image, 'source_commit': subprocess.check_output(
                  ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'runner_sha256': sha(Path(__file__)), 'suites': [],
              'full_v05_accepted': False, 'full_v06_accepted': False}
    print('Evidence: ' + str(output), flush=True)
    for name, script, options, minimum in SUITES:
        if args.suite and name not in args.suite:
            continue
        command = [sys.executable, '-X', 'utf8', str(ROOT / 'conformance' / script),
                   *options, '--image', image]
        print('Running ' + name, flush=True)
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                             encoding='utf-8', errors='replace')
        log = output / (name + '.log')
        log.write_text(run.stdout + '\n' + run.stderr, encoding='utf-8', newline='\n')
        stage = {'suite': name, 'command': command, 'exit_code': run.returncode,
                 'log': {'path': str(log), 'sha256': sha(log)}, 'passed': False}
        try:
            stage['raw'] = validate_report(report_from_stdout(run.stdout), image, minimum)
            if run.returncode:
                raise ValueError('Runner exited with ' + str(run.returncode))
            stage['passed'] = True
        except (ValueError, OSError, KeyError, TypeError) as error:
            stage['error'] = str(error)
        result['suites'].append(stage)
        if not stage['passed']:
            result['state'] = 'failed'
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n',
                                          encoding='utf-8', newline='\n')
        print(name + ': ' + ('PASS' if stage['passed'] else 'FAIL ' + stage['error']), flush=True)
        if not stage['passed']:
            return 1
    result.update(passed=True, state='completed')
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n',
                                      encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
