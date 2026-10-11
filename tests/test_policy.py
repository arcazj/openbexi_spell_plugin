from contextvars import copy_context
import pytest

from openbexi_spell.common import (ABORT, CANCEL, HANDLE, NOACTION, RECHECK, REPEAT, RESEND,
    SKIP, Action, ChangeLanguageConfig, DriverException, Handle, ProcedureAbort, SpellContext, _context)


def test_configuration_precedence_and_atomic_procedure_local_change():
    context = SpellContext({"GetTM": {"Timeout": 9, "Wait": False}})
    context.change("GetTM", Timeout=7, Wait=True)
    assert context.effective("GetTM", Timeout=3)["Timeout"] == 3
    assert context.effective("GetTM")["Timeout"] == 7
    assert context.effective("GetTM")["Wait"] is True
    with pytest.raises(ValueError):
        context.change("GetTM", Timeout=1, Bogus=True)
    assert context.effective("GetTM")["Timeout"] == 7
    assert SpellContext().effective("GetTM")["Timeout"] == 30
    assert SpellContext().effective("GetTM")["Wait"] is False


def test_change_language_config_callable_and_context_isolation():
    def GetTM():
        pass
    GetTM._spell_name = "GetTM"
    token = _context.set(SpellContext())
    try:
        ChangeLanguageConfig(GetTM, Wait=True)
        def independent():
            _context.set(SpellContext())
            ChangeLanguageConfig(GetTM, Wait=False)
            return _context.get().effective(GetTM)["Wait"]
        assert copy_context().run(independent) is False
        assert _context.get().effective(GetTM)["Wait"] is True
    finally:
        _context.reset(token)


def test_appendix_defaults_and_affected_errata_decisions():
    context = SpellContext()
    assert context.effective("GetTM")["HandleError"] is False
    assert context.effective("GetTM")["Notify"] is False
    assert context.effective("GetTM")["OnFalse"] == NOACTION
    assert context.effective("Verify")["OnFalse"] == ABORT | SKIP | REPEAT | CANCEL
    assert context.effective("Prompt")["PromptFailure"] is True


@pytest.mark.parametrize("target,modifiers", [("GetTM", {"Wait": 1}), ("GetTM", {"Timeout": float("nan")}),
    ("Verify", {"Retries": True}), ("Verify", {"Retries": 101}), ("Display", {"Verbosity": -1}),
    ("GetTM", {"ValueFormat": "invalid"}), ("GetTM", {"OnTrue": HANDLE}),
    ("GetTM", {"OnFalse": RECHECK}), ("Verify", {"OnFailure": RESEND}),
    ("Send", {"OnFailure": 512}), ("Send", {"OnFailure": True}), ("unknown", {}),
    ("GetTM", {"PromptFailure": False}), ("Verify", {"PromptUser": False}),
    ("GetTM", {"OnFailure": HANDLE, "PromptFailure": False})])
def test_invalid_modifiers_fail_before_adapter_invocation(target, modifiers):
    with pytest.raises((TypeError, ValueError)):
        SpellContext().effective(target, **modifiers)


@pytest.mark.parametrize("outcome,action,expected", [(True, NOACTION, True), (False, NOACTION, False),
    (False, SKIP, True), (True, CANCEL, False), (True, SKIP, True), (False, CANCEL, False)])
def test_result_actions_are_distinct_from_operation_failures(outcome, action, expected):
    result = SpellContext().invoke("Verify", lambda config: outcome,
        modifiers={"OnTrue": action, "OnFalse": action, "PromptUser": False})
    assert result is expected


def test_driver_failure_is_catchable_by_default_and_handle_has_custom_code():
    failure = DriverException("acquisition failed", "source unavailable", code=5, operation="GetTM")
    def unavailable(config):
        raise failure
    with pytest.raises(DriverException) as observed:
        SpellContext().invoke("GetTM", unavailable)
    assert observed.value is failure and observed.value.reason == "source unavailable"
    with pytest.raises(Handle) as handled:
        SpellContext().invoke("GetTM", unavailable,
            modifiers={"HandleError": True, "OnFailure": HANDLE | CANCEL, "FailureCode": 42},
            prompt=lambda name, choices, error: HANDLE)
    assert handled.value.code == 42 and handled.value.failure is failure


@pytest.mark.parametrize("action,expected", [(SKIP, True), (CANCEL, False), (NOACTION, None)])
def test_handled_failure_automatic_dispositions(action, expected):
    def failure(config):
        raise DriverException("failed")
    assert SpellContext().invoke("GetTM", failure,
        modifiers={"HandleError": True, "PromptFailure": False, "OnFailure": action}) is expected


@pytest.mark.parametrize("action,target", [(REPEAT, "GetTM"), (RECHECK, "Verify"), (RESEND, "Send")])
def test_retry_runs_actual_adapter_again_and_settles_the_new_result(action, target):
    calls = []
    def adapter(config):
        calls.append(config)
        if len(calls) == 1:
            raise DriverException("first attempt rejected", effect_certainty="NO_EFFECT")
        return True
    result = SpellContext().invoke(target, adapter,
        modifiers={"HandleError": True, "PromptFailure": False, "OnFailure": action, "OnFalse": NOACTION})
    assert result is True and len(calls) == 2


def test_false_verification_rechecks_instead_of_treating_false_as_driver_failure():
    values = iter([False, True])
    assert SpellContext().invoke("Verify", lambda config: next(values),
        modifiers={"OnFalse": RECHECK, "PromptUser": False}) is True


@pytest.mark.parametrize("action", [REPEAT, RESEND, SKIP, CANCEL, NOACTION])
def test_uncertain_command_effect_cannot_be_retried_or_hidden(action):
    calls = []
    def uncertain(config):
        calls.append(1)
        raise DriverException("acknowledgement lost", effect_certainty="UNKNOWN")
    with pytest.raises(DriverException, match="acknowledgement lost"):
        SpellContext().invoke("Send", uncertain,
            modifiers={"HandleError": True, "OnFailure": action, "PromptFailure": False})
    assert len(calls) == 1


def test_retry_budget_interactive_choice_and_abort():
    calls = []
    def rejected(config):
        calls.append(1)
        raise DriverException("rejected")
    with pytest.raises(DriverException, match="retry budget exhausted"):
        SpellContext(retry_budget=2).invoke("GetTM", rejected,
            modifiers={"HandleError": True, "OnFailure": REPEAT, "PromptFailure": False})
    assert len(calls) == 3
    with pytest.raises(ValueError, match="outside"):
        SpellContext().invoke("Verify", lambda config: False, prompt=lambda *args: RESEND)
    with pytest.raises(DriverException, match="prompt service"):
        SpellContext().invoke("Verify", lambda config: False)
    aborted = []
    with pytest.raises(ProcedureAbort):
        SpellContext().invoke("Verify", lambda config: False,
            modifiers={"OnFalse": ABORT, "PromptUser": False}, abort=lambda *args: aborted.append(args))
    assert len(aborted) == 1


def test_notify_false_suppresses_item_feedback_without_changing_return():
    notices = []
    context = SpellContext()
    assert context.invoke("Verify", lambda config: True, notify=lambda *args: notices.append(args)) is True
    assert notices == []
    assert context.invoke("Verify", lambda config: True, modifiers={"Notify": True},
                          notify=lambda *args: notices.append(args)) is True
    assert notices == [("Verify", True, None)]


def test_nonboolean_item_feedback_and_text_verbosity_are_independent():
    notices = []
    context = SpellContext(max_verbosity=3)
    assert context.invoke("GetTM", lambda config: 42, modifiers={"Notify": True, "Verbosity": 999},
                          notify=lambda *args: notices.append(args)) == 42
    assert notices == [("GetTM", 42, None)]
    assert context.text_visible("GetTM")
    assert not context.text_visible("GetTM", Verbosity=999)
