"""Procedure-local defaults and shared result/failure policy.

The runtime supplies operation, prompt, notification and abort services. This
module never substitutes a successful result for an unavailable service.
"""
from __future__ import annotations

from contextvars import ContextVar
from enum import IntFlag
import math
from .api import DriverException


class Action(IntFlag):
    NOACTION = 0
    ABORT = 1
    SKIP = 2
    CANCEL = 4
    REPEAT = 8
    RECHECK = 16
    RESEND = 32
    RESUME = 64
    HANDLE = 128


NOACTION, ABORT, SKIP, CANCEL, REPEAT, RECHECK, RESEND, RESUME, HANDLE = (
    Action[name] for name in ("NOACTION", "ABORT", "SKIP", "CANCEL", "REPEAT", "RECHECK", "RESEND", "RESUME", "HANDLE"))
ENG, RAW = "ENG", "RAW"


class Handle(Exception):
    def __init__(self, code=0, *, failure=None):
        if type(code) is not int:
            raise TypeError("Handle code must be an integer")
        self.code, self.failure = code, failure
        super().__init__("SPELL failure delegated to procedure", code)


class ProcedureAbort(BaseException):
    """Internal termination signal; the broker must settle the actual execution."""


_COMMON = {"HandleError": False, "OnFailure": ABORT | SKIP | REPEAT | CANCEL,
           "PromptFailure": True, "OnTrue": NOACTION, "OnFalse": NOACTION,
           "PromptUser": True, "Notify": False, "Verbosity": 0, "FailureCode": 0}
_FUNCTIONS = {
    "GetTM": {"Wait": False, "Timeout": 30.0, "ValueFormat": ENG},
    "Verify": {"Timeout": 30.0, "Delay": 0.0, "Retries": 2, "Tolerance": 0.0,
               "IgnoreCase": False, "AdjLimits": True, "ValueFormat": ENG,
               "Op": "EQ", "OnFalse": ABORT | SKIP | REPEAT | CANCEL},
    "WaitFor": {"Timeout": 30.0},
    "BuildTC": {},
    "Send": {"Timeout": 60.0, "Confirm": False, "AdjLimits": True},
    "Display": {"Severity": "INFORMATION"},
    "Prompt": {"Type": "OK", "Options": None, "Default": None, "Timeout": 0},
}
_BOOLEANS = {"HandleError", "PromptFailure", "PromptUser", "Notify", "Wait", "IgnoreCase", "AdjLimits", "Confirm"}
_NUMBERS = {"Timeout", "Delay", "Tolerance"}
_ACTIONS = {"OnFailure", "OnTrue", "OnFalse"}
_RETRY_ACTIONS = REPEAT | RECHECK | RESEND | RESUME
_KNOWN_BITS = sum(int(value) for value in Action)


def _name(function):
    name = function if type(function) is str else getattr(function, "_spell_name", None)
    if name not in _FUNCTIONS:
        raise ValueError("configuration target must be an approved SPELL function")
    return name


def _validate(name, values):
    allowed = set(_COMMON) | set(_FUNCTIONS[name])
    unknown = set(values) - allowed
    if unknown:
        raise ValueError("unsupported " + name + " modifier: " + sorted(unknown)[0])
    for key, value in values.items():
        if key in _BOOLEANS and type(value) is not bool:
            raise TypeError(key + " must be Boolean")
        if key in _NUMBERS and (type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= 86400):
            raise ValueError(key + " must be finite and in 0..86400")
        if key in {"Retries", "Verbosity", "FailureCode"} and type(value) is not int:
            raise TypeError(key + " must be an integer")
        if key == "Retries" and not 0 <= value <= 100:
            raise ValueError("Retries must be in 0..100")
        if key == "Verbosity" and not 0 <= value <= 1_000_000:
            raise ValueError("Verbosity is out of range")
        if key in _ACTIONS:
            if type(value) not in {int, Action} or value < 0 or int(value) & ~_KNOWN_BITS:
                raise ValueError(key + " requires known SPELL actions")
            if value & HANDLE and key != "OnFailure":
                raise ValueError("HANDLE applies only to operation failure")
            if value & RECHECK and name != "Verify":
                raise ValueError("RECHECK applies only to Verify")
            if value & (RESEND | RESUME) and name != "Send":
                raise ValueError("RESEND and RESUME apply only to Send")
        if key == "ValueFormat" and value not in {ENG, RAW}:
            raise ValueError("ValueFormat must be ENG or RAW")
        if key == "Severity" and value not in {"INFORMATION", "WARNING", "ERROR"}:
            raise ValueError("unsupported Severity")
        if key == "Type" and value not in {"OK", "YES_NO", "ALPHA", "NUM", "DATE", "COMBO", "LIST"}:
            raise ValueError("unsupported Prompt Type")
        if key == "Op" and value not in {"EQ", "NE", "LT", "LE", "GT", "GE"}:
            raise ValueError("unsupported comparison")


class SpellContext:
    def __init__(self, configured_defaults=None, *, max_verbosity=5, retry_budget=100):
        if type(max_verbosity) is not int or max_verbosity < 0:
            raise ValueError("invalid configured maximum verbosity")
        if type(retry_budget) is not int or not 0 <= retry_budget <= 100:
            raise ValueError("invalid runtime retry budget")
        self.max_verbosity, self.retry_budget = max_verbosity, retry_budget
        self.configured, self.changed = {}, {}
        for function, values in (configured_defaults or {}).items():
            name = _name(function)
            _validate(name, values)
            self.configured[name] = dict(values)

    def change(self, function, **values):
        name = _name(function)
        _validate(name, values)
        self.changed[name] = {**self.changed.get(name, {}), **values}

    def effective(self, function, **values):
        name = _name(function)
        _validate(name, values)
        result = {**_COMMON, **_FUNCTIONS[name], **self.configured.get(name, {}),
                  **self.changed.get(name, {}), **values}
        for key in _ACTIONS:
            result[key] = Action(result[key])
        for key, interactive in (("OnFailure", "PromptFailure"), ("OnTrue", "PromptUser"), ("OnFalse", "PromptUser")):
            if not result[interactive] and int(result[key]).bit_count() > 1:
                raise ValueError("automatic " + key + " requires one action")
        if result["OnFailure"] & HANDLE and not result["PromptFailure"]:
            raise ValueError("HANDLE requires an interactive failure choice")
        return result

    def text_visible(self, function, **values):
        return self.effective(function, **values)["Verbosity"] <= self.max_verbosity

    def invoke(self, function, operation, *, modifiers=None, prompt=None, notify=None, abort=None):
        """Apply policy to a real adapter call; uncertain effects are never retried."""
        name = _name(function)
        config = self.effective(name, **(modifiers or {}))
        retries = 0
        while True:
            failure = None
            try:
                result = operation(config)
            except DriverException as exc:
                failure = exc
                if not config["HandleError"]:
                    if config["Notify"] and notify is not None:
                        try:
                            notify(name, None, failure)
                        except Exception:
                            raise failure from None
                    raise
                action, interactive = config["OnFailure"], config["PromptFailure"]
                result = None
            else:
                if type(result) is not bool:
                    if config["Notify"] and notify is not None:
                        notify(name, result, None)
                    return result
                action = config["OnTrue"] if result else config["OnFalse"]
                interactive = config["PromptUser"]
            if config["Notify"] and notify is not None:
                try:
                    notify(name, result, failure)
                except Exception:
                    if failure is not None:
                        raise failure from None
                    raise
            if interactive and action != NOACTION:
                if prompt is None:
                    raise DriverException("interactive policy requires a controlling prompt service", operation=name)
                chosen = prompt(name, action, failure if failure is not None else result)
                if type(chosen) not in {int, Action} or int(chosen).bit_count() != 1 or chosen & action != chosen:
                    raise ValueError("prompt selected an action outside the declared choices")
                action = Action(chosen)
            if action == ABORT:
                if abort is not None:
                    abort(name, failure)
                raise ProcedureAbort(name)
            if action == HANDLE:
                raise Handle(config["FailureCode"], failure=failure)
            if failure is not None and (failure.effect_certainty == "UNKNOWN" or
                                       name == "Send" and failure.effect_certainty == "CONFIRMED"):
                # SKIP/CANCEL cannot erase an uncertain command effect either.
                raise failure
            if action == NOACTION:
                # An ignored failure remains an explicit None, never generic True.
                return result
            if action == SKIP:
                return True
            if action == CANCEL:
                return False
            if action & _RETRY_ACTIONS:
                if retries >= self.retry_budget:
                    raise DriverException("runtime retry budget exhausted", operation=name)
                retries += 1
                continue
            raise ValueError("unsupported action disposition")


_context = ContextVar("spell_procedure_context", default=None)


def current_context():
    context = _context.get()
    if context is None:
        context = SpellContext()
        _context.set(context)
    return context


def ChangeLanguageConfig(function, **modifiers):
    current_context().change(function, **modifiers)
