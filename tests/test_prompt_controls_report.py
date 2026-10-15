"""A passing prompt-control summary cannot conceal altered native observations."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
import prompt_control_report as controls


@pytest.fixture(scope='module')
def proof():
    canonical = json.loads((ROOT / 'conformance/evidence/prompt_controls.json').read_bytes())
    paths = {name: Path(row['path']) for name, row in canonical['raw'].items()}
    for name, path in paths.items():
        assert controls.sha(path) == canonical['raw'][name]['sha256']
    return paths


def qualify(paths):
    return controls.qualify(paths['stress'], paths['modes'], paths['timed'], paths['native_pair'], paths['abort_stress'])


def test_controls_prove_behavior_without_promoting_language_requirements(proof):
    report = qualify(proof)
    assert report['passed'] and report['qualified_contracts'] == []
    assert len(report['native_sources']) == 4
    assert len(report['retained_failures']) == 5
    assert not report['full_v05_accepted'] and not report['full_v06_accepted']


@pytest.mark.parametrize('mutation', [
    'missing-trial', 'later-answer', 'reordered-answers', 'multiple-prompts',
    'different-runtime', 'changed-events', 'altered-procedure', 'abort-still-waiting',
    'early-parent-return', 'manual-started', 'wrong-open-mode', 'lost-child',
    'cleanup-error', 'abort-stress-incomplete',
])
def test_altered_prompt_or_child_evidence_is_rejected(proof, tmp_path, mutation):
    kind = 'stress' if mutation in {
        'missing-trial', 'later-answer', 'reordered-answers', 'multiple-prompts',
        'different-runtime', 'changed-events', 'altered-procedure',
    } else 'modes'
    if mutation == 'abort-stress-incomplete':
        kind = 'abort_stress'
    original = proof[kind]
    report = json.loads(original.read_bytes())
    shutil.copytree(original.parent / 'workspace', tmp_path / 'workspace')
    if kind == 'stress':
        row = report['checks']['duplicate-0:boundary']
        if mutation == 'missing-trial':
            del report['checks']['duplicate-23:boundary']
        elif mutation == 'later-answer':
            row['result']['answer'] = 'A'
        elif mutation == 'reordered-answers':
            row['answers'].reverse()
        elif mutation == 'multiple-prompts':
            row['prompts'] *= 2
        elif mutation == 'different-runtime':
            report['runtime_image'] = 'sha256:' + '0' * 64
        elif mutation == 'changed-events':
            (tmp_path / 'workspace/duplicate-0-boundary/events.json').write_text('[]')
        else:
            (tmp_path / 'workspace/duplicate-0-boundary/main.py').write_text('pass\n')
    elif kind == 'abort_stress':
        del report['checks']['blocking-abort-11']
    else:
        row = report['checks']['blocking-abort']
        if mutation == 'abort-still-waiting':
            row['observations'][-1]['child_status'] = 'PROMPT'
        elif mutation == 'early-parent-return':
            held = next(r for r in row['observations'] if r['phase'] == 'child-awaiting-input')
            held['parent_returned'] = True
        elif mutation == 'manual-started':
            row = report['checks']['manual-blocking']
            next(r for r in row['observations'] if r['phase'] == 'before-manual-run')['child_started'] = True
        elif mutation == 'wrong-open-mode':
            row['child_info']['OpenMode'] = '{Automatic:True,Visible:True,Blocking:False}'
        elif mutation == 'lost-child':
            row['inventory']['ExecutorList'] = ''
        else:
            row['cleanup_error'] = 'Executor remained alive'
    target = tmp_path / 'result.json'
    target.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError)):
        qualify({**proof, kind: target})
