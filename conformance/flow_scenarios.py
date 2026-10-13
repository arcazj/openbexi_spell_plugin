"""Traced procedure bodies for FLOW; no imported oracle controls execution."""
import textwrap

HEADER = """from pathlib import Path
import json
from spell.runtime import Step, Goto
from spell.lang.functions import DisplayStep, Pause, Abort, Finish
from spell.lang.functions import SetUserAction, EnableUserAction, DisableUserAction, DismissUserAction
from spell.lang.constants import INFORMATION, WARNING, ERROR
from spell.lang.modifiers import Severity, HandleError
from spell.lib.exception import SyntaxException
"""

SCENARIOS = {}


def scenario(name, source, **expected):
    SCENARIOS[name] = dict(source=HEADER + textwrap.dedent(source), **expected)


scenario('goto-literal', """
    visited = []
    Step('A1', 'First stage')
    visited.append('A1')
    Goto('A2')
    visited.append('must not execute')
    Step('A2', 'Last stage')
    visited.append('A2')
    assert visited == ['A1', 'A2']
    Path('effects.json').write_text(json.dumps(visited))
""", status='FINISHED', effects=['A1', 'A2'])
scenario('goto-backward', """
    count = 0
    Step('LOOP', 'Same frame backward jump')
    count += 1
    if count < 3:
        Goto('LOOP')
    assert count == 3
    Path('effects.json').write_text(json.dumps(count))
""", status='FINISHED', effects=3)
scenario('goto-dynamic-title', """
    title = 'Title from variable'
    Goto('TARGET')
    Path('skipped.txt').write_text('forward jump failed')
    Step('TARGET', title)
    assert not Path('skipped.txt').exists()
    Path('effects.json').write_text(json.dumps(title))
""", status='FINISHED', effects='Title from variable')
scenario('goto-missing', """
    Goto('MISSING')
    Path('continued.txt').write_text('must not continue')
""", status='ABORTED', no_continue=True)
scenario('goto-cross-function', """
    def child():
        Step('CHILD', 'Other function frame')
        return
    Goto('CHILD')
    Path('continued.txt').write_text('must not continue')
""", status='ABORTED', no_continue=True)
scenario('display-not-target', """
    DisplayStep('DISPLAY', 'Not a jump label')
    Goto('DISPLAY')
    Path('continued.txt').write_text('must not continue')
""", status='ABORTED', no_continue=True)
scenario('step-invalid-recovery', """
    errors = []
    try:
        Step()
    except TypeError:
        errors.append('step-arity')
    try:
        Goto()
    except TypeError:
        errors.append('goto-arity')
    try:
        Step('BAD', 'Invalid keyword', invalid=True)
    except TypeError:
        errors.append('step-keyword')
    assert errors == ['step-arity', 'goto-arity', 'step-keyword']
    Step('RECOVERED', 'Valid step after rejected calls')
    Path('effects.json').write_text(json.dumps(errors))
""", status='FINISHED', effects=['step-arity', 'goto-arity', 'step-keyword'])
scenario('display-step', """
    identifier = 'DYNAMIC'
    title = 'Computed title'
    DisplayStep(identifier, title + ' value')
    DisplayStep('', '')
    DisplayStep('RESTORED', 'Final display')
    Path('effects.json').write_text(json.dumps(True))
""", status='FINISHED', effects=True)
scenario('display-invalid-recovery', """
    try:
        DisplayStep('missing-description')
    except TypeError:
        pass
    else:
        raise AssertionError('Missing DisplayStep argument accepted')
    DisplayStep('RECOVERED', 'Display still works')
    Path('effects.json').write_text(json.dumps(True))
""", status='FINISHED', effects=True)
scenario('goto-title-function', """
    def make_title():
        with Path('evaluations.txt').open('a') as stream:
            stream.write('evaluated\\n')
        return 'Title from actual function'
    assert not Path('evaluations.txt').exists()
    Goto('TARGET')
    Path('skipped.txt').write_text('function-title jump failed')
    Step('TARGET', make_title())
    assert not Path('skipped.txt').exists()
    assert Path('evaluations.txt').read_text() == 'evaluated\\n'
    Path('effects.json').write_text(json.dumps(True))
""", status='FINISHED', effects=True)
scenario('goto-title-conditional', """
    title = ''
    Goto('TARGET')
    Path('skipped.txt').write_text('conditional-title jump failed')
    Step('TARGET', title or 'Fallback title')
    assert not Path('skipped.txt').exists()
    Path('effects.json').write_text(json.dumps(True))
""", status='FINISHED', effects=True)
scenario('goto-nested-frame', """
    def child():
        visited = []
        Step('FIRST', 'Child first')
        Goto('LAST')
        visited.append('must not execute')
        Step('LAST', 'Child last')
        return visited
    assert child() == []
    Path('effects.json').write_text(json.dumps(True))
""", status='FINISHED', effects=True)
scenario('goto-into-loop', """
    Goto('INSIDE')
    Path('normal.txt').write_text('normal continuation')
    for index in range(1):
        Step('INSIDE', 'Cannot enter loop without iterator')
        assert Path('normal.txt').read_text() == 'normal continuation'
    Path('effects.json').write_text(json.dumps('normal continuation'))
""", status='FINISHED', effects='normal continuation')
scenario('goto-dynamic-target', """
    target = 'LAST'
    Goto(target)
    Path('skipped.txt').write_text('dynamic jump failed')
    Step('LAST', 'Runtime target expression')
    assert not Path('skipped.txt').exists()
    Path('effects.json').write_text(json.dumps(True))
""", status='FINISHED', effects=True)
scenario('step-boundary', """
    Step('', '')
    Step('étape', 'Unicode title')
    Path('effects.json').write_text(json.dumps(True))
""", status='FINISHED', effects=True)
scenario('finish-custom', """
    try:
        Finish('FLOW finished successfully')
        Path('continued.txt').write_text('must not continue')
    finally:
        Path('cleanup.txt').write_text('finish cleanup')
""", status='FINISHED', no_continue=True, cleanup='finish cleanup')
scenario('finish-default', """
    Finish()
    Path('continued.txt').write_text('must not continue')
""", status='FINISHED', no_continue=True)
scenario('finish-empty', """
    Finish('')
    Path('continued.txt').write_text('must not continue')
""", status='FINISHED', no_continue=True)
scenario('abort-custom', """
    try:
        Abort('FLOW explicitly aborted')
        Path('continued.txt').write_text('must not continue')
    finally:
        Path('cleanup.txt').write_text('abort cleanup')
""", status='ABORTED', no_continue=True, cleanup='abort cleanup')
scenario('abort-default', """
    Abort()
    Path('continued.txt').write_text('must not continue')
""", status='ABORTED', no_continue=True)
scenario('abort-empty', """
    Abort('')
    Path('continued.txt').write_text('must not continue')
""", status='ABORTED', no_continue=True)
scenario('terminal-invalid-recovery', """
    errors = []
    try:
        Abort('too', 'many')
    except TypeError:
        errors.append('Abort')
    try:
        Finish('too', 'many')
    except TypeError:
        errors.append('Finish')
    assert errors == ['Abort', 'Finish']
    Path('effects.json').write_text(json.dumps(errors))
    Finish('Recovered from invalid terminal calls')
""", status='FINISHED', effects=['Abort', 'Finish'])
scenario('pause-resume', """
    Path('stage.txt').write_text('first')
    Pause()
    Path('stage.txt').write_text('second')
    Pause()
    Path('effects.json').write_text(json.dumps(['resumed twice']))
""", status='FINISHED', effects=['resumed twice'], pauses=['first', 'second'])
scenario('pause-invalid-recovery', """
    try:
        Pause(['TM1', 1], HandleError=False)
    except SyntaxException:
        Path('rejected.txt').write_text('missing Timeout')
    else:
        raise AssertionError('Conditional Pause without Timeout accepted')
    Path('stage.txt').write_text('recovered')
    Pause()
    Path('effects.json').write_text(json.dumps(True))
""", status='FINISHED', effects=True, pauses=['recovered'])
scenario('user-actions', """
    def first_action():
        with Path('actions.txt').open('a') as stream:
            stream.write('first\\n')
        return
    def replacement_action():
        with Path('actions.txt').open('a') as stream:
            stream.write('replacement\\n')
        return
    Path('actions.txt').write_text('')
    assert SetUserAction(first_action, 'Primary action', Severity=WARNING) is True
    Path('stage.txt').write_text('enabled')
    Pause()
    assert DisableUserAction() is True
    assert DisableUserAction() is True
    Path('stage.txt').write_text('disabled')
    Pause()
    assert EnableUserAction() is True
    assert EnableUserAction() is True
    Path('stage.txt').write_text('reenabled')
    Pause()
    assert SetUserAction(replacement_action, 'Replacement action') is True
    Path('stage.txt').write_text('replaced')
    Pause()
    assert SetUserAction(replacement_action, 'Critical action', Severity=ERROR) is True
    Path('stage.txt').write_text('critical')
    Pause()
    assert DismissUserAction() is True
    Path('stage.txt').write_text('dismissed')
    Pause()
    assert DismissUserAction() is True
    Path('stage.txt').write_text('dismissed-twice')
    Pause()
    errors = []
    try:
        SetUserAction(42, 'Not a function', HandleError=False)
    except SyntaxException:
        errors.append('function')
    try:
        SetUserAction(first_action, 42, HandleError=False)
    except SyntaxException:
        errors.append('label')
    try:
        SetUserAction(first_action, HandleError=False)
    except SyntaxException:
        errors.append('arity')
    assert errors == ['function', 'label', 'arity']
    assert SetUserAction(first_action, 'Recovered action') is True
    Path('stage.txt').write_text('recovered')
    Pause()
    DismissUserAction()
    Path('effects.json').write_text(json.dumps(errors))
""", status='FINISHED', effects=['function', 'label', 'arity'], actions={
    'enabled': ['first'], 'disabled': ['first'], 'reenabled': ['first', 'first'],
    'replaced': ['first', 'first', 'replacement'],
    'critical': ['first', 'first', 'replacement', 'replacement'],
    'dismissed': ['first', 'first', 'replacement', 'replacement'],
    'dismissed-twice': ['first', 'first', 'replacement', 'replacement'],
    'recovered': ['first', 'first', 'replacement', 'replacement', 'first'],
})
scenario('user-action-invalid-arity', """
    def valid_action():
        with Path('actions.txt').open('a') as stream:
            stream.write('valid\\n')
        return
    Path('actions.txt').write_text('')
    SetUserAction(valid_action, 'Preserved action', {Severity: INFORMATION})
    Path('stage.txt').write_text('initial')
    Pause()
    errors = []
    try:
        EnableUserAction(1, HandleError=False)
    except SyntaxException:
        errors.append('Enable')
    try:
        DisableUserAction(1, HandleError=False)
    except SyntaxException:
        errors.append('Disable')
    try:
        DismissUserAction(1, HandleError=False)
    except SyntaxException:
        errors.append('Dismiss')
    try:
        SetUserAction(valid_action, 'Bad arity', 'extra', HandleError=False)
    except SyntaxException:
        errors.append('Set arity')
    try:
        SetUserAction(valid_action, 'Bad severity', Severity=True, HandleError=False)
    except SyntaxException:
        errors.append('Set boolean severity')
    try:
        SetUserAction(valid_action, 'Bad severity', Severity=99, HandleError=False)
    except SyntaxException:
        errors.append('Set unknown severity')
    assert errors == ['Enable', 'Disable', 'Dismiss', 'Set arity', 'Set boolean severity', 'Set unknown severity'], errors
    Path('stage.txt').write_text('after-rejection')
    Pause()
    DisableUserAction()
    EnableUserAction()
    DismissUserAction()
    SetUserAction(valid_action, 'Recovered action', {Severity: INFORMATION})
    Path('stage.txt').write_text('recovered')
    Pause()
    DismissUserAction()
    Path('effects.json').write_text(json.dumps(errors))
""", status='FINISHED',
     effects=['Enable', 'Disable', 'Dismiss', 'Set arity', 'Set boolean severity', 'Set unknown severity'],
     actions={'initial': ['valid'], 'after-rejection': ['valid', 'valid'],
              'recovered': ['valid', 'valid', 'valid']})
scenario('user-action-running', """
    import time
    def running_action():
        Path('actions.txt').write_text('running action executed')
        return
    SetUserAction(running_action, 'While running')
    Path('ready.txt').write_text('ready')
    attempts = 0
    while not Path('actions.txt').exists():
        time.sleep(0.05)
        attempts += 1
        assert attempts < 100, 'No action from native controller'
    DismissUserAction()
    Path('effects.json').write_text(json.dumps(Path('actions.txt').read_text()))
""", status='FINISHED', effects='running action executed', running_action=True)
scenario('user-action-callback-error', """
    def broken_action():
        raise ValueError('FLOW callback fault')
    def recovered_action():
        with Path('actions.txt').open('a') as stream:
            stream.write('recovered\\n')
        return
    Path('actions.txt').write_text('')
    SetUserAction(broken_action, 'Broken callback')
    Path('stage.txt').write_text('broken')
    Pause()
    SetUserAction(recovered_action, 'Recovered callback')
    Path('stage.txt').write_text('recovered')
    Pause()
    DismissUserAction()
    Path('effects.json').write_text(json.dumps('callback recovered'))
""", status='FINISHED', effects='callback recovered',
     actions={'broken': [], 'recovered': ['recovered']})
