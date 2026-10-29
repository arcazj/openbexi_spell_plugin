"""Native warnings must not substitute for, or erase, lifecycle audit receipts."""

import ast
from copy import deepcopy
from pathlib import Path
import uuid
import zipfile

import pytest


@pytest.fixture(scope="module")
def assess():
    source = Path(__file__).resolve().parents[2] / "scripts/qualify_v08_native_launch.py"
    function = next(
        node
        for node in ast.parse(source.read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "audit_native_lifecycle_receipts"
    )
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[function.name]


def cohort(child_gate=True, warnings=1):
    executions = [dict(id=str(uuid.uuid5(uuid.NAMESPACE_OID, str(i)))) for i in range(10)]
    bodies = []

    def event(execution, message, scope):
        bodies.append(
            dict(
                request_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, str(len(bodies)))),
                execution_id=execution["id"],
                message=message,
                severity=1 if scope != 1 else 8,
                scope=scope,
                control_epoch=1,
                worker_incarnation="original-worker",
            )
        )

    for index, execution in enumerate(executions):
        members = (3 if index == 0 else 2) if child_gate else 1
        for member in range(members):
            event(execution, "Procedure started: member " + str(member), 1)
            event(execution, "Procedure finished: member " + str(member), 1)
    for index in range(warnings):
        event(executions[0], "Procedure awaiting prompt answer", 2 if index == 0 else 4)
    receipts = [(body["request_id"], body["execution_id"]) for body in bodies]
    return executions, bodies, receipts


def test_lifecycle_category_is_bound_to_frozen_controller_and_ev_defaults():
    archive = Path(__file__).resolve().parents[2] / "docs/reference/SPELL2.6.10-src.zip"
    with zipfile.ZipFile(archive) as frozen:
        controller = frozen.read("lib/SPELL_EXC/src/SPELLcontroller.C").decode()
        adapter = frozen.read("src/spell/spell/lib/adapter/ev.py").decode()
        constants = frozen.read("src/spell/spell/lang/constants.py").decode()
    assert 'callMethod(evIfc,"raiseEvent",evMsg,NULL)' in controller
    assert "Severity:INFORMATION" in adapter and "Scope:SCOPE_PROC" in adapter
    namespace = {}
    nodes = [
        node
        for node in ast.parse(constants).body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id in {"INFORMATION", "SCOPE_PROC"}
            for target in node.targets
        )
    ]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "frozen/constants.py", "exec"), namespace)
    assert namespace["INFORMATION"] == 8 and namespace["SCOPE_PROC"] == 1


@pytest.mark.parametrize("child_gate", [False, True])
@pytest.mark.parametrize("warnings", [0, 1, 2])
def test_all_native_events_keep_unique_receipts_and_original_lifecycle_counts(
    assess, child_gate, warnings
):
    executions, bodies, receipts = cohort(child_gate, warnings)
    retained = deepcopy(bodies)
    result = assess(executions, bodies, receipts, child_gate)
    expected = 42 if child_gate else 20
    assert result["passed"] and not result["failures"]
    assert result["native_lifecycle_events_persisted"] == expected
    assert result["native_non_lifecycle_events_persisted"] == warnings
    assert result["native_driver_events_persisted"] == expected + warnings
    assert (
        result["all_event_bodies_checked"]
        == result["all_receipt_identities_checked"]
        == expected + warnings
    )
    assert bodies == retained
    assert all(
        row["started"] == row["finished"] == row["expected_started"]
        for row in result["native_lifecycle_counts"]
    )


@pytest.mark.parametrize(
    "damage",
    [
        "missing_finish",
        "duplicate_finish",
        "warning_replaces_finish",
        "duplicate_receipt",
        "foreign_execution",
        "missing_body",
        "unreceipted_body",
        "invalid_scope",
        "receipt_execution_differs",
        "request_id_reused",
        "system_warning_substitutes_finish",
        "configuration_substitutes_start",
        "wrong_severity_substitutes_finish",
    ],
)
def test_extra_native_warnings_cannot_hide_missing_duplicate_or_misbound_audits(assess, damage):
    executions, bodies, receipts = cohort()
    if damage == "missing_finish":
        bodies.pop(41)
        receipts.pop(41)
    elif damage == "duplicate_finish":
        body = dict(bodies[41], request_id=str(uuid.uuid4()))
        bodies.append(body)
        receipts.append((body["request_id"], body["execution_id"]))
    elif damage == "warning_replaces_finish":
        bodies[41].update(message="Procedure awaiting prompt answer", scope=2)
    elif damage == "duplicate_receipt":
        receipts.append(receipts[-1])
    elif damage == "foreign_execution":
        bodies[-1]["execution_id"] = str(uuid.uuid4())
    elif damage == "missing_body":
        bodies.pop()
    elif damage == "unreceipted_body":
        receipts.pop()
    elif damage == "invalid_scope":
        bodies[-1]["scope"] = 8
    elif damage == "receipt_execution_differs":
        receipts[-1] = (receipts[-1][0], executions[1]["id"])
    elif damage == "request_id_reused":
        bodies[-1]["request_id"] = bodies[0]["request_id"]
    elif damage == "system_warning_substitutes_finish":
        bodies[41].update(scope=2, severity=1)
    elif damage == "configuration_substitutes_start":
        bodies[40]["scope"] = 4
    else:
        bodies[41]["severity"] = 1
    before = deepcopy(bodies)
    result = assess(executions, bodies, receipts, True)
    assert not result["passed"] and result["failures"]
    assert result["all_event_bodies_checked"] == len(bodies)
    assert result["all_receipt_identities_checked"] == len(receipts)
    assert bodies == before
