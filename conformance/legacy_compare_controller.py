"""Run original native CLI procedures, retaining actual source and terminal logs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path('/workspace')
sys.path.insert(0, str(ROOT))
from legacy_compare_cases import CASES, INVALID, FIXTURE
from legacy_compare_provenance import capture

checks = {}
for name, source in {**CASES, **INVALID}.items():
    project = ROOT / name
    try:
        example = json.loads(subprocess.check_output(['spell-native', 'init-example', str(project)], text=True))
        procedure = project / 'data/Procedures/main.py'
        procedure.write_text(source + ("\nfrom spell.lang.functions import Display\nDisplay('LEGACY_COMPARE_PASSED')\n" if name in CASES else ''), encoding='utf-8')
        (procedure.parent / 'comparison_fixture.py').write_text(FIXTURE, encoding='utf-8')
        run = subprocess.run(['spell-native', 'run', '-f', str(procedure), '-c', example['config'], '-n', 'example', '-d'],
            env=dict(os.environ, **example['environment']), capture_output=True, timeout=40)
        log = run.stdout + run.stderr
        (project / 'native.log').write_bytes(log)
        assert b'AddressSanitizer:' not in log and b'runtime error:' not in log
        if name in CASES:
            assert run.returncode == 0 and b'[ STATUS  ] FINISHED' in log and b'LEGACY_COMPARE_PASSED' in log, 'Procedure did not finish successfully'
        else:
            assert b'Error during preparation: Syntax error:' in log and b'LEGACY_COMPARE_PASSED' not in log, 'Malformed grammar was not rejected'
        checks[name] = dict(passed=True, source=source, expected='FINISHED' if name in CASES else 'SyntaxError', exit_code=run.returncode)
    except Exception as error:
        checks[name] = dict(passed=False, source=source, error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc())
    (ROOT / 'checks.json').write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
(ROOT / 'runtime.json').write_text(json.dumps(capture(), indent=2) + '\n', encoding='utf-8')
raise SystemExit(any(row['passed'] is not True for row in checks.values()))
