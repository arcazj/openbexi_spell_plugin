"""Qualify v0.7 from installed wheels, real DSS transports and owned workers."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ide', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--wheels', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('workflow_evidence', ROOT / 'distribution/workflow_evidence.py')
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    spec = importlib.util.spec_from_file_location('installed_driver_oracles', ROOT / 'distribution/installed_driver_oracles.py')
    oracles = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracles)
    bindings = json.loads(args.wheels.read_bytes())
    installed = evidence.installed_wheels(bindings, args.wheels.parent)
    owners = {'openbexi_runtime':'openbexi-ide', 'openbexi_spell_shared':'openbexi-spell-shared',
              'openbexi_spell_host':'openbexi-spell-host', 'openbexi_spell_dss':'openbexi-spell-dss',
              'dss':'openbexi-spell-plugin'}
    imports = evidence.imported_modules(bindings, owners, args.wheels.parent)
    os.environ['OPENBEXI_NATIVE_TEST_IMAGE'] = evidence.exact_image(args.image)
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    os.environ.pop('PYTEST_ADDOPTS', None)
    tests = args.output / 'tests'
    tests.mkdir()
    shutil.copy2(args.ide / 'run_cli.py', args.output / 'run_cli.py')
    # Reuse only the Qt fixture setup; never prepend a repository source tree.
    fixture = (args.ide / 'tests/conftest.py').read_text(encoding='utf-8')
    fixture = fixture.replace('sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))', '')
    (tests / 'conftest.py').write_text(fixture, encoding='utf-8', newline='\n')
    ide = ['native_driver_acceptance.py', 'test_shared_backends.py', 'test_sessions.py',
           'test_durable_sessions.py', 'test_execution_sessions.py', 'test_authority_maintenance.py',
           'test_session_tls.py', 'test_session_backpressure.py']
    plugin = ['test_original_driver.py', 'test_operational_journal.py', 'kafka_driver_acceptance.py']
    inputs = {}
    for root, names in ((args.ide, ide), (ROOT, plugin)):
        for name in names:
            original = root / 'tests' / name
            source = original.read_text(encoding='utf-8')
            inputs[str(original.resolve())] = evidence.sha(original)
            if name in {'native_driver_acceptance.py', 'test_original_driver.py'}:
                source = oracles.adapt(name, source)
            (tests / name).write_text(source, encoding='utf-8', newline='\n')
    copied = {p.name:evidence.sha(p) for p in tests.glob('*.py')}
    config = args.output / 'pytest.ini'
    config.write_text('[pytest]\n', encoding='utf-8')
    selected = [*plugin, 'native_driver_acceptance.py', 'test_shared_backends.py',
                'test_durable_sessions.py', 'test_authority_maintenance.py',
                'test_session_tls.py', 'test_session_backpressure.py']
    code = pytest.main([*(str(tests / name) for name in selected), '-q', '-c', str(config),
                        '-o', 'faulthandler_timeout=90', '--junitxml=' + str(args.output / 'tests.xml')])
    assert installed == evidence.installed_wheels(bindings, args.wheels.parent)
    assert imports == evidence.imported_modules(bindings, owners, args.wheels.parent)
    assert all(evidence.sha(name) == digest for name, digest in inputs.items())
    assert copied == {p.name:evidence.sha(p) for p in tests.glob('*.py')}
    suites = ET.parse(args.output / 'tests.xml').getroot().iter('testsuite')
    totals = {k:0 for k in ('tests', 'errors', 'failures', 'skipped')}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, 0))
    result = dict(passed=code == 0 and totals['errors'] == totals['failures'] == totals['skipped'] == 0,
                  image=args.image, installed_wheels=installed, imported_modules=imports,
                  tests=totals, source_inputs=inputs, copied_tests=copied,
                  harness_sha256=evidence.sha(Path(__file__)), oracles_sha256=evidence.sha(ROOT / 'distribution/installed_driver_oracles.py'))
    (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(passed=result['passed'], tests=totals, output=str(args.output))), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
