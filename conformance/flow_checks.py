"""Independent expectations for observed native FLOW effects and IPC."""
import hashlib
import json

PREFIX = 'CMP-LRM244-'
DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')


def compact(observation):
    row = {key: value for key, value in observation.items() if key not in ('events', 'asrun')}
    messages = [event.get('message', {}) for event in observation['events']]
    row['messages'] = [message for message in messages if message.get('id') in (
        'MSG_WRITE', 'MSG_SET_UACTION', 'MSG_UNSET_UACTION', 'MSG_ENABLE_UACTION')]
    row['stages'] = sorted({(message['fields']['StageId'], message['fields'].get('StageTl', ''))
                           for message in messages if 'StageId' in message.get('fields', {})})
    row['wire_sha256'] = hashlib.sha256(json.dumps(observation['events'], sort_keys=True).encode()).hexdigest()
    row['asrun_actions'] = [line for content in observation.get('asrun', {}).values()
                           for line in content.splitlines() if '\tUACTION\t' in line]
    row['asrun_sha256'] = {name: hashlib.sha256(content.encode()).hexdigest()
                          for name, content in observation.get('asrun', {}).items()}
    return row


def qualify(observations):
    rows = {name: compact(row) for name, row in observations.items()}
    checks = {}

    def check(group, contracts, dimensions, oracle, proof=None):
        for dimension, scenarios in zip(DIMENSIONS, dimensions):
            row = dict(dimension=dimension, contracts=[PREFIX + key for key in contracts],
                       oracle=oracle, scenarios=scenarios, passed=False)
            try:
                assert all(rows[name]['passed'] for name in scenarios), {
                    name: rows.get(name, {}).get('error', 'scenario failed')
                    for name in scenarios if not rows.get(name, {}).get('passed')}
                if proof:
                    proof(dimension)
                row['passed'] = True
            except Exception as error:
                row['error'] = type(error).__name__ + ': ' + str(error)
            checks[group + ':' + dimension] = row

    def stage(name, identifier, title):
        assert (identifier, title) in rows[name]['stages'], (name, rows[name]['stages'])

    def step_proof(dimension):
        if dimension == 'positive':
            stage('goto-literal', 'A1', 'First stage')
            stage('goto-literal', 'A2', 'Last stage')
        elif dimension == 'boundary':
            stage('goto-dynamic-title', 'TARGET', 'Title from variable')
            stage('goto-title-function', 'TARGET', 'Title from actual function')
            stage('goto-title-conditional', 'TARGET', 'Fallback title')
            stage('step-boundary', 'étape', 'Unicode title')
        elif dimension == 'recovery':
            stage('step-invalid-recovery', 'RECOVERED', 'Valid step after rejected calls')

    check('step', ['FUNCTION-CANDIDATE-STEP', 'EXAMPLE-128', 'SECTION-4-14-1-091'], [
        ['goto-literal'], ['goto-dynamic-title', 'goto-title-function', 'goto-title-conditional', 'step-boundary'],
        ['step-invalid-recovery'], ['step-invalid-recovery', 'goto-nested-frame']],
        'LRM p75: literal Step label, observed native stage id/title; computed title evaluated only on execution; invalid binding arguments reject; real subsequent Step recovers.', step_proof)
    check('goto', ['FUNCTION-CANDIDATE-GOTO', 'EXAMPLE-129', 'SECTION-4-14-2-092'], [
        ['goto-literal'], ['goto-backward', 'goto-dynamic-target', 'goto-nested-frame'],
        ['goto-missing', 'goto-cross-function', 'goto-into-loop'],
        ['step-invalid-recovery', 'goto-title-function', 'goto-title-conditional']],
        'LRM pp75-76: forward skips effects, backward executes exactly three stages, runtime target and same-function jump work; unknown/cross-function targets abort; loop-entry transfer rejected with normal sequential effect preserved; fresh worker and invalid-call recovery.')

    def display_proof(dimension):
        if dimension in ('positive', 'boundary'):
            stage('display-step', 'DYNAMIC', 'Computed title value')
            stage('display-step', 'RESTORED', 'Final display')
        elif dimension == 'recovery':
            stage('display-invalid-recovery', 'RECOVERED', 'Display still works')
    check('display-step', ['FUNCTION-DISPLAYSTEP', 'EXAMPLE-130'], [
        ['display-step'], ['display-step'], ['display-not-target', 'display-invalid-recovery'],
        ['display-invalid-recovery']],
        'LRM p76: dynamic id/title appear in native stage notifications, including empty/default display boundary; DisplayStep never registers a jump label; invalid arity rejects and subsequent display recovers.', display_proof)

    def terminal_proof(kind, dimension):
        expected = {'finish': ['FLOW finished successfully', 'Completed Execution'],
                    'abort': ['FLOW explicitly aborted', 'Execution Aborted']}
        if dimension in ('positive', 'boundary'):
            name = kind + ('-custom' if dimension == 'positive' else '-default')
            text = '\n'.join(message.get('fields', {}).get('Text', '') for message in rows[name]['messages'])
            assert expected[kind][0 if dimension == 'positive' else 1] in text, text
    for kind in ('finish', 'abort'):
        check(kind, ['FUNCTION-' + kind.upper()], [
            [kind + '-custom'], [kind + '-default', kind + '-empty'],
            ['terminal-invalid-recovery'], ['terminal-invalid-recovery']],
            'LRM pp76-77: optional/default/empty terminal messages, exact FINISHED versus ABORTED native status, finally cleanup and no later effects; invalid arity does not terminate and a fresh executor performs valid Finish.',
            lambda dimension, kind=kind: terminal_proof(kind, dimension))
    check('pause', ['FUNCTION-PAUSE'], [
        ['pause-resume'], ['pause-resume'], ['pause-invalid-recovery'], ['pause-invalid-recovery']],
        'LRM pp76-77: actual PAUSED status and no continuation until explicit CMD_RUN, two consecutive pauses; invalid conditional form without Timeout rejects, then unconditional pause/resume succeeds. Conditional telemetry semantics remain outside this evidence.')

    def action_proof(dimension):
        observed = {row['stage']: row for row in rows['user-actions']['action_states']}
        if dimension == 'positive':
            assert observed['enabled']['info']['ActionEnabled'] == 'true'
            assert observed['enabled']['info']['ActionLabel'] == 'Primary action'
            assert rows['user-action-running']['running_action_info']['ExecutorStatus'] == 'RUNNING'
        elif dimension == 'boundary':
            assert observed['disabled']['info']['ActionEnabled'] == 'false'
            assert observed['disabled']['info']['ActionLabel'] == 'Primary action'
            assert observed['reenabled']['info']['ActionEnabled'] == 'true'
            for key in ('dismissed', 'dismissed-twice'):
                assert 'ActionLabel' not in observed[key]['info']
            assert [observed[key]['info']['ActionSeverity'] for key in ('enabled', 'replaced', 'critical')] == ['WARN', 'INFO', 'ERROR']
            records = '\n'.join(rows['user-actions']['asrun_actions'])
            assert '\tPrimary action\tWARN' in records
            assert '\tReplacement action\tINFO' in records
            assert '\tCritical action\tERROR' in records
        elif dimension == 'failure':
            preserved = {row['stage']: row for row in rows['user-action-invalid-arity']['action_states']}
            for key in ('initial', 'after-rejection'):
                assert preserved[key]['info']['ActionLabel'] == 'Preserved action'
                assert preserved[key]['info']['ActionEnabled'] == 'true'
            errors = '\n'.join(message.get('fields', {}).get('Text', '') for message in rows['user-action-callback-error']['messages'])
            assert 'FLOW callback fault' in errors and 'Failed to execute user action' in errors
        else:
            assert observed['recovered']['info']['ActionLabel'] == 'Recovered action'
            assert observed['recovered']['effects'] == ['first', 'first', 'replacement', 'replacement', 'first']
            assert rows['user-action-callback-error']['effects'] == 'callback recovered'
    check('user-action', [
        'FUNCTION-SETUSERACTION', 'FUNCTION-ENABLEUSERACTION', 'FUNCTION-DISABLEUSERACTION',
        'FUNCTION-DISMISSUSERACTION', 'EXAMPLE-132', 'EXAMPLE-133', 'EXAMPLE-134',
        'ERRATUM-USER-ACTION-DISABLE', 'SECTION-4-14-4-094'], [
        ['user-actions', 'user-action-running'], ['user-actions'],
        ['user-action-invalid-arity', 'user-action-callback-error'],
        ['user-actions', 'user-action-invalid-arity', 'user-action-callback-error']],
        'LRM pp77-78 and original helper/executor: one actual native callback; independent CMD_ACTION proves effects and disabled/dismissed suppression, configuration retained versus reset, named severity in IPC and AsRun, idempotence, rejected calls preserve configuration, callback error is observed and subsequent callback recovers.', action_proof)

    for group, contracts, dependencies in (
        ('terminal-section', ['EXAMPLE-131', 'SECTION-4-14-3-093'], ['pause', 'abort', 'finish']),
        ('flow-section', ['SECTION-4-14-090'], ['step', 'goto', 'display-step', 'pause', 'abort', 'finish', 'user-action']),
    ):
        for dimension in DIMENSIONS:
            keys = [dependency + ':' + dimension for dependency in dependencies]
            checks[group + ':' + dimension] = dict(
                dimension=dimension, contracts=[PREFIX + key for key in contracts],
                oracle='Every explicitly listed native control-flow child check must pass this dimension.',
                dependencies=keys, passed=all(checks[key]['passed'] for key in keys))
    return checks, rows
