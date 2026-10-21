"""Run preserved v0.6 evidence tests and current v0.7 runtime/recipe tests.

Historical reports bind the exact sources they originally qualified. They must
be checked in that frozen revision, rather than relabeled as v0.7 evidence.
Current installed operational and native gates remain separate requirements.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '1c8679c64e1ee25d2441b0c10f35678c36367e6c'
LIVE = '''block_execution command_catalog_rpc command_execution command_group_rpc
command_rpc command_setting_bounds conformance_clock conformance_io
context_snapshot_patches dss_engine dss_transports evidence_database
gcs_display_application group_execution legacy_compare_patches legacy_compare_syntax
limit_algorithm limit_arguments limit_definitions limit_features_rpc
limit_telemetry_sources manoeuvre_clock_rpc memory_features_rpc onboard_schedule
operational_journal original_driver plugin policy proc_dictionary_patches
procedure_library prompt_startup_patches ranging_complete_rpc rng_state_patch
shutdown_pause_recipe telemetry_comparison_boundaries telemetry_features_rpc time
uplink_groups wait_interrupt_patches'''.split()


def totals(path):
    result = {key:0 for key in ('tests', 'errors', 'failures', 'skipped')}
    for suite in ET.parse(path).getroot().iter('testsuite'):
        for key in result:
            result[key] += int(suite.get(key, 0))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--historical-python', type=Path, default=Path(sys.executable))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.baseline,text=True).strip() == BASELINE
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=args.baseline,text=True).strip()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    result = dict(passed=False, baseline_commit=BASELINE, stages={})
    for label, root, selected in [('historical',args.baseline,[]),
                                  ('current',ROOT,['tests/test_'+name+'.py' for name in LIVE])]:
        env = dict(os.environ, PYTHONPATH=str(root / 'driver_plugin/src'))
        interpreter = str(args.historical_python) if label == 'historical' else sys.executable
        command = [interpreter,'-m','pytest',*selected,'-q','-x',
                   '--junitxml='+str(args.output / (label+'.xml'))]
        with (args.output / (label+'.log')).open('wb') as log:
            run = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        result['stages'][label] = dict(exit_code=run.returncode, tests=totals(args.output / (label+'.xml')),
                                        command=command, selected=selected or 'entire baseline repository suite')
        (args.output / 'result.json').write_text(json.dumps(result,indent=2)+'\n')
        if run.returncode:
            return run.returncode
    result['passed'] = all(row['exit_code'] == 0 and row['tests']['failures'] == row['tests']['errors'] == 0
                           for row in result['stages'].values())
    result['historical_note'] = 'Frozen evidence tests stay at their original accepted sources; current runtime tests and installed/native gates qualify the changed release.'
    (args.output / 'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
