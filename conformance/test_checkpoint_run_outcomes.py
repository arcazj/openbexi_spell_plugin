"""A successful controller process must not hide failed or missing controls."""
import copy
import importlib.util
from pathlib import Path

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=['identity', 'error', 'error-ipc'])
def gate(request):
    options = dict(modes=['ON_LINE', 'ON_STEP'], cases=['one', 'two'], executions=['fresh', 'resume'])
    checks = {mode+':'+case:dict(passed=True) for mode in options['modes'] for case in options['cases']}
    if request.param == 'identity':
        module = load('checkpoint_identity_run')
        evaluate = lambda rows: module.checks_passed(rows, options)
    else:
        module = load('checkpoint_error_run')
        ipc = request.param == 'error-ipc'
        if not ipc:
            checks = {name+':'+execution:dict(passed=True) for name in checks for execution in options['executions']}
        evaluate = lambda rows: module.checks_passed(rows, options, ipc)
    return evaluate, checks


def test_complete_success(gate):
    evaluate, checks = gate
    assert evaluate(checks)


@pytest.mark.parametrize('mutation', ['failed', 'missing', 'extra', 'empty', 'error', 'cleanup_error', 'drain_error', 'sanitizer_failure', 'truthy'])
def test_failed_or_incomplete_controls(gate, mutation):
    evaluate, original = gate
    checks = copy.deepcopy(original)
    first = next(iter(checks))
    if mutation == 'failed': checks[first]['passed'] = False
    elif mutation == 'truthy': checks[first]['passed'] = 'true'
    elif mutation == 'missing': del checks[first]
    elif mutation == 'extra': checks['unexpected'] = dict(passed=True)
    elif mutation == 'empty': checks.clear()
    else: checks[first][mutation] = 'failure'
    assert not evaluate(checks)
