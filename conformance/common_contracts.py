"""LRM pp.26-31 and 116-117 policy oracles in the original native executor.

No helpers, registry entries, CIF methods or executor methods are replaced.
Failure inputs are absent files/blackboard keys and failed compare-and-set.
The external DAP controller answers real native prompts and repairs one file.
Cross-family modifiers remain open until their service-specific tests exist.
"""
import json
from pathlib import Path

from spell.lang.functions import (
    ChangeLanguageConfig, ClearSharedData, Display, GetSharedData, GetTM,
    OpenFile, SetSharedData,
)
from spell.lang.constants import ABORT, CANCEL, HANDLE, NOACTION, REPEAT, SKIP
from spell.lang.modifiers import HandleError, Notify, OnFalse, OnTrue, PromptUser, Wait
from spell.lang.helpers.datahelper import SetSharedData_Helper
from spell.lang.helpers.genhelper import Display_Helper
from spell.lang.helpers.tmhelper import GetTM_Helper
from spell.lib.exception import DriverException, Handle, SyntaxException
from spell.lib.registry import REGISTRY

PREFIX = 'CMP-LRM244-'
DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')
cases = {}
checks = {}
active = None
key = 'common-conformance-owned'
missing = 'common-conformance-absent'


def equal(actual, expected):
    assert actual == expected and type(actual) is type(expected), (actual, expected)


def rejects(operation, kind):
    try:
        operation()
    except kind as error:
        return error
    raise AssertionError('Expected ' + kind.__name__)


def plan(choices, answer, repair=None):
    active['prompts'].append({'choices': choices, 'answer': answer, 'repair': repair})
    Path('common-active.json').write_text(json.dumps(active), encoding='utf-8')


def case(name, contracts, positive, boundary, failure, recovery=None, oracle=None):
    cases[name] = dict(contracts=[PREFIX + item for item in contracts],
        positive=positive, boundary=boundary, failure=failure,
        recovery=recovery or (lambda: (failure(), positive())),
        oracle=oracle or 'LRM 2.4.4 pp.26-31,116-117; literal results, unchanged blackboard values and real controller prompt choices')


def set_value(value=10, **config):
    return SetSharedData(Name=key, Value=value, **config)


def fail_read(**config):
    return GetSharedData(missing, **config)


def stored(expected):
    equal(GetSharedData(key, HandleError=False), expected)


def success():
    equal(set_value(10, OnTrue=NOACTION, OnFalse=NOACTION), True)
    stored(10)


def failed_compare(**config):
    return SetSharedData(Name=key, Value=99, Expected=-1, **config)


def result_table():
    # The twelve combinations in the LRM pp.29-30 table, literal expectations.
    for result in (True, False):
        for interactive in (True, False):
            for selected in ('none', 'true', 'false'):
                matching = selected == ('true' if result else 'false')
                cfg = ABORT | SKIP | CANCEL if interactive else SKIP
                if matching and interactive:
                    plan(['ABORT', 'SKIP', 'CANCEL'], 'SKIP')
                success()
                options = dict(PromptUser=interactive,
                    OnTrue=cfg if selected == 'true' else NOACTION,
                    OnFalse=cfg if selected == 'false' else NOACTION)
                observed = set_value(11, **options) if result else failed_compare(**options)
                equal(observed, True if matching else result)
                stored(11 if result else 10)


def prompt_flags():
    # A result prompt must occur even when failure prompting is disabled.
    for result in (True, False):
        success()
        plan(['SKIP', 'CANCEL'], 'CANCEL')
        cfg = dict(PromptUser=True, PromptFailure=False, OnFailure=SKIP,
                   OnTrue=SKIP | CANCEL if result else NOACTION,
                   OnFalse=SKIP | CANCEL if not result else NOACTION)
        equal(set_value(12, **cfg) if result else failed_compare(**cfg), False)
        stored(12 if result else 10)
    # An operation failure prompts independently of PromptUser=False.
    plan(['ABORT', 'SKIP'], 'SKIP')
    equal(fail_read(PromptUser=False, PromptFailure=True, OnFailure=ABORT | SKIP), None)
    # Existing callers may inherit interactive options for a dormant result.
    original = REGISTRY['CTX'].getFunctionConfig('SetSharedData').copy()
    try:
        ChangeLanguageConfig(SetSharedData, OnFalse=SKIP | CANCEL)
        equal(set_value(10, PromptUser=False), True)
        rejects(lambda: failed_compare(PromptUser=False), SyntaxException)
        stored(10)
    finally:
        defaults = REGISTRY['CTX'].getFunctionConfig('SetSharedData')
        defaults.clear()
        defaults.update(original)


def invalid_actions():
    success()
    for name in ('OnTrue', 'OnFalse', 'OnFailure'):
        for value in (True, 'SKIP', -1, 0):
            rejects(lambda: SetSharedData_Helper().configure(**{name: value}), SyntaxException)
    for name, flag in (('OnTrue', 'PromptUser'), ('OnFalse', 'PromptUser'), ('OnFailure', 'PromptFailure')):
        rejects(lambda: set_value(99, **{name: SKIP | CANCEL, flag: False}), SyntaxException)
    stored(10)


case('result-policy', ['MODIFIER-ONTRUE', 'MODIFIER-ONFALSE', 'MODIFIER-PROMPTUSER',
     'OUTCOME-BOOLEAN-TRUE', 'OUTCOME-BOOLEAN-FALSE', 'SECTION-3-4-019', 'EXAMPLE-023'],
     result_table, prompt_flags, invalid_actions)


def skip_cancel(action):
    success()
    equal(failed_compare(PromptUser=False, OnFalse=action), action == SKIP)
    stored(10)  # Policy changes the returned value, not the failed mutation.
    equal(set_value(12, PromptUser=False, OnTrue=action), action == SKIP)
    stored(12)  # CANCEL after success does not undo an already completed mutation.


def skip_cancel_prompt(action):
    success()
    plan(['ABORT', 'SKIP', 'CANCEL'], 'SKIP' if action == SKIP else 'CANCEL')
    equal(failed_compare(PromptUser=True, OnFalse=ABORT | SKIP | CANCEL), action == SKIP)
    stored(10)


for name, action in (('SKIP', SKIP), ('CANCEL', CANCEL)):
    case('action-' + name.lower(), ['CONSTANT-ACTION-' + name],
         lambda value=action: skip_cancel(value), lambda value=action: skip_cancel_prompt(value),
         invalid_actions)


def noaction():
    success()
    equal(failed_compare(PromptUser=False, OnFalse=NOACTION), False)
    stored(10)
    equal(fail_read(PromptFailure=False, OnFailure=NOACTION), None)


case('noaction', ['CONSTANT-ACTION-NOACTION'], noaction,
     lambda: (success(), equal(failed_compare(PromptUser=True, OnFalse=NOACTION), False)),
     invalid_actions)


def failure_policy():
    for interactive_result in (True, False):
        plan(['ABORT', 'SKIP'], 'SKIP')
        equal(fail_read(PromptUser=interactive_result, PromptFailure=True, OnFailure=ABORT | SKIP), None)
        equal(fail_read(PromptUser=interactive_result, PromptFailure=False, OnFailure=SKIP), None)


def single_action_prompt():
    plan(['SKIP'], 'SKIP')
    equal(fail_read(PromptFailure=True, OnFailure=SKIP), None)
    equal(fail_read(PromptFailure=False, OnFailure=SKIP), None)


case('failure-policy', ['MODIFIER-ONFAILURE', 'MODIFIER-PROMPTFAILURE',
     'ERRATUM-PROMPT-FAILURE-MODIFIERS', 'EXAMPLE-021', 'SECTION-3-3-018',
     'SYNTAX-ACTION-COMBINATION', 'OUTCOME-OPERATION-FAILURE'],
     failure_policy, single_action_prompt, invalid_actions)


def error_propagation():
    error = rejects(lambda: fail_read(HandleError=False), DriverException)
    assert missing in str(error)
    assert isinstance(error.message, str) and isinstance(error.reason, str)
    assert str(error) == repr(error)
    success()  # The native process lock is released even when an error escapes.


def default_handle():
    plan(['ABORT', 'SKIP'], 'SKIP')
    equal(fail_read(OnFailure=ABORT | SKIP), None)
    error_propagation()
    ChangeLanguageConfig(GetSharedData, HandleError=False)
    try:
        rejects(fail_read, DriverException)
        plan(['SKIP'], 'SKIP')
        equal(fail_read(HandleError=True, OnFailure=SKIP), None)
    finally:
        ChangeLanguageConfig(GetSharedData, HandleError=True)


def bad_booleans():
    for name in ('HandleError', 'PromptUser', 'PromptFailure', 'Notify'):
        for value in (0, 1, 'False', None):
            rejects(lambda: SetSharedData_Helper().configure(**{name: value}), SyntaxException)


case('handle-error', ['MODIFIER-HANDLEERROR', 'ERRATUM-HANDLEERROR-DEFAULT',
     'EXAMPLE-024', 'SECTION-3-5-020', 'SYNTAX-TRY-EXCEPT-DRIVER', 'TYPE-DRIVEREXCEPTION'],
     error_propagation, default_handle, bad_booleans)


def custom_handle(code):
    plan(['SKIP', 'HANDLE'], 'HANDLE')
    error = rejects(lambda: fail_read(OnFailure=HANDLE | SKIP, FailureCode=code), Handle)
    equal(error.code, code)
    equal(error.type, 'DATA')
    equal(error.item, missing)
    success()


def invalid_handle():
    rejects(lambda: SetSharedData_Helper().configure(OnFailure=HANDLE, PromptFailure=False), SyntaxException)
    rejects(lambda: SetSharedData_Helper().configure(OnFailure=HANDLE, FailureCode='bad'), SyntaxException)
    rejects(lambda: SetSharedData_Helper().configure(OnFailure=NOACTION, PromptFailure=True), SyntaxException)


case('custom-handle', ['CONSTANT-ACTION-HANDLE', 'MODIFIER-FAILURECODE', 'TYPE-HANDLEEXCEPTION'],
     lambda: custom_handle(42), lambda: (custom_handle(0), custom_handle(-1)), invalid_handle)


def config_defaults():
    # Same function selected by the normative Example 20, with real CTX defaults.
    original = REGISTRY['CTX'].getFunctionConfig('GetTM').copy()
    interface = REGISTRY['CTX'].getInterfaceConfig('TM').copy()
    try:
        ChangeLanguageConfig(GetTM, Wait=True, Notify=False)
        helper = GetTM_Helper()
        helper.configure()
        equal(helper.getConfig(Wait), True)
        equal(helper.getConfig(Notify), False)
        equal(REGISTRY['CTX'].getInterfaceConfig('TM'), interface)
        helper = GetTM_Helper()
        helper.configure({Wait:False}, config={Wait:True}, Wait=False)
        equal(helper.getConfig(Wait), False)
        equal(REGISTRY['CTX'].getFunctionConfig('GetTM')[Wait], True)
    finally:
        config = REGISTRY['CTX'].getFunctionConfig('GetTM')
        config.clear()
        config.update(original)
        REGISTRY['CIF'].resetVerbosity()


def config_empty():
    # Display is absent from upstream language.xml. Valid defaults can be added.
    original = REGISTRY['CTX'].getFunctionConfig('Display')
    saved = original.copy() if original is not None else {}
    try:
        ChangeLanguageConfig(Display, Notify=False)
        helper = Display_Helper()
        helper.configure()
        equal(helper.getConfig(Notify), False)
        helper.configure(Notify=True)
        equal(helper.getConfig(Notify), True)
        ChangeLanguageConfig(Display)  # Empty change leaves the defaults intact.
        equal(REGISTRY['CTX'].getFunctionConfig('Display')[Notify], False)
    finally:
        config = REGISTRY['CTX'].getFunctionConfig('Display')
        if config is not None:
            config.clear()
            config.update(saved)
        REGISTRY['CIF'].resetVerbosity()


def config_failure():
    rejects(lambda: ChangeLanguageConfig(42, Wait=True), SyntaxError)
    rejects(lambda: ChangeLanguageConfig(lambda: None, Wait=True), SyntaxError)
    previous = REGISTRY['CTX'].getFunctionConfig('GetTM').copy()
    rejects(lambda: ChangeLanguageConfig(GetTM, Wait=True, UnknownCommonModifier=1), SyntaxException)
    equal(REGISTRY['CTX'].getFunctionConfig('GetTM'), previous)
    rejects(lambda: ChangeLanguageConfig(GetTM, Wait=True, HandleError='False'), SyntaxException)
    equal(REGISTRY['CTX'].getFunctionConfig('GetTM'), previous)


case('configuration', ['FUNCTION-CHANGELANGUAGECONFIG', 'SECTION-3-2-016',
     'SECTION-3-2-1-017', 'EXAMPLE-019', 'EXAMPLE-020', 'SYNTAX-KEYWORD-MODIFIER'],
     config_defaults, config_empty, config_failure)


def repeat_repair():
    path = 'common-repair-' + str(len(checks)) + '.txt'
    plan(['ABORT', 'REPEAT', 'SKIP'], 'REPEAT', repair=path)
    handle = OpenFile(path, OnFailure=ABORT | REPEAT | SKIP)
    try:
        equal(handle.read(), ['repaired by controller'])
    finally:
        handle.close()


def repeat_twice():
    path = 'common-repair-boundary-' + str(len(checks)) + '.txt'
    plan(['REPEAT', 'SKIP'], 'REPEAT')
    plan(['REPEAT', 'SKIP'], 'REPEAT', repair=path)
    handle = OpenFile(path, OnFailure=REPEAT | SKIP)
    try:
        equal(handle.read(), ['repaired by controller'])
    finally:
        handle.close()


case('repeat', ['CONSTANT-ACTION-REPEAT'], repeat_repair, repeat_twice,
     lambda: (plan(['REPEAT', 'SKIP'], 'SKIP'), equal(OpenFile('absent-file.txt', OnFailure=REPEAT | SKIP), None)))


def true_false():
    success()
    equal(failed_compare(OnFalse=NOACTION), False)
    stored(10)


case('operation-success', ['OUTCOME-OPERATION-SUCCESS'], true_false,
     lambda: (equal(set_value(0), True), stored(0), equal(set_value(False), True), stored(False)),
     error_propagation)


for name, functions in cases.items():
    for dimension in DIMENSIONS:
        identifier = name + ':' + dimension
        active = {'check': identifier, 'prompts': []}
        Path('common-active.json').write_text(json.dumps(active), encoding='utf-8')
        row = dict(dimension=dimension, contracts=functions['contracts'],
                   oracle=functions['oracle'], passed=False)
        try:
            functions[dimension]()
            row['passed'] = True
        except Exception as error:
            row['error'] = type(error).__name__ + ': ' + str(error)
        row['expected_prompts'] = active['prompts']
        checks[identifier] = row
        Path('common-results.json').write_text(json.dumps({'checks':checks}, indent=2), encoding='utf-8')

ClearSharedData(key, HandleError=False)
print('COMMON_CONFORMANCE_RESULT', sum(row['passed'] for row in checks.values()), len(checks), flush=True)
