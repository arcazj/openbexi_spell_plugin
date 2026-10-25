"""Private native boundary: unsupported mutations never gain effect authority."""

import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from openbexi_spell_server.contracts import Fault
import test_child_gate as gates

ROOT = Path(__file__).resolve().parents[2]


def test_compiled_native_policy_closes_unsupported_messages_and_requests(tmp_path):
    source = tmp_path / "policy.cpp"
    source.write_text(r"""
#include "mutation_policy.H"
#include <cassert>
int main() {
    for (const auto id: {"CMD_RUN", "CMD_STEP", "CMD_PAUSE"}) {
        assert(v08_command_supported(id));
        assert(!v08_message_disabled(id, false));
        assert(v08_message_disabled(id, true));
        assert(!v08_context_forward_disabled(id));
        assert(!v08_external_command_disabled(id, true));
    }
    for (const auto id: {"CMD_ABORT", "CMD_CLOSE", "CMD_BLOCK", "CMD_STOP",
                         "CMD_SCRIPT", "CMD_GOTO", "CMD_STEP_OVER", "CMD_SKIP",
                         "CMD_RELOAD", "CMD_ACTION", "CMD_FINISH", "CMD_INTERRUPT",
                         "CMD_FUTURE_UNREVIEWED"}) {
        assert(!v08_command_supported(id));
        assert(v08_message_disabled(id, false));
        assert(v08_message_disabled(id, true));
        assert(v08_context_forward_disabled(id));
        assert(v08_external_command_disabled(id, true));
        assert(!v08_external_command_disabled(id, false));
    }
    assert(v08_message_disabled("MSG_ANSWER", false));
    assert(v08_message_disabled("MSG_CANCEL", false));
    assert(v08_context_forward_disabled("MSG_ANSWER"));
    assert(v08_context_forward_disabled("MSG_CANCEL"));
    assert(!v08_context_forward_disabled("MSG_LOADED"));
    assert(!v08_context_forward_disabled("RSP_DONE"));
    assert(!v08_context_forward_disabled("REQ_EXEC_STATUS"));
    assert(v08_external_command_disabled("MSG_ANSWER", true));
    assert(!v08_external_command_disabled("CMD_PAUSE", false));
    for (const auto id: {"REQ_SET_CONFIG", "REQ_SET_BREAKPOINT", "REQ_CLEAR_BREAKPOINT",
                         "REQ_CHANGE_VARIABLE", "REQ_CHANGE_RESOURCE", "REQ_UPD_DICTIONARY",
                         "REQ_FUTURE_UNREVIEWED"}) assert(!v08_request_supported(id));
    for (const auto id: {"REQ_GET_CONFIG", "REQ_EXEC_STATUS", "REQ_GET_VARIABLES",
                         "REQ_WVARIABLES_ENABLED", "REQ_GET_RESOURCES",
                         "REQ_DRESOURCES_ENABLED", "REQ_GET_DICTIONARY"})
        assert(v08_request_supported(id));
}
""")
    binary = tmp_path / "policy"
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(ROOT / "host_runtime/native"),
            str(source),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    subprocess.run([str(binary)], check=True, capture_output=True, timeout=5)


def test_native_context_and_executor_hooks_precede_effect_admission():
    """The compiled allowlist must be called at the actual native boundaries."""
    builder = (ROOT / "host_runtime/build_admission_context.py").read_text()
    forward = (ROOT / "host_runtime/native/admission_gate.H").read_text()
    consumption = (ROOT / "host_runtime/native/execution_gate.H").read_text()
    assert builder.count("v08_admit_native_run(m_model, msg);") == 1
    assert builder.count("v08_consume_native_run(m_procId, cmd);") == 1
    forward = forward.split("static void v08_admit_native_run", 1)[1]
    consumption = consumption.split("static void v08_consume_native_run", 1)[1]
    forward_guard = "v08_context_forward_disabled(command)"
    final_guard = "v08_external_command_disabled(command.id, command.v08External)"
    assert forward.index(forward_guard) < forward.index("v08_native_request({")
    assert consumption.index(final_guard) < consumption.index("v08_native_request({")


@pytest.fixture
def denied_server():
    server = gates.module.NativeAdmissionServer.__new__(gates.module.NativeAdmissionServer)
    server.disabled_mutations = set()
    server.reports = []
    server.report = lambda event, **body: server.reports.append((event, body))
    return server


def denial(**changes):
    return dict(
        schema="openbexi.native-denied/1", instance_id="root#1", operation="CMD_SCRIPT", **changes
    )


def test_authenticated_denial_diagnostic_is_never_an_allow_or_a_control_dispatch(denied_server):
    for _ in range(2):
        with pytest.raises(ValueError, match="Unqualified native mutation rejected"):
            denied_server.dispatch("executor", "root#1", denial())
    assert denied_server.disabled_mutations == {("root#1", "CMD_SCRIPT")}
    assert len(denied_server.reports) == 1


@pytest.mark.parametrize(
    "changed",
    [
        dict(instance_id="other#1"),
        dict(operation="bad\nline"),
        dict(operation=[]),
        dict(operation="A" * 65),
        dict(token="copied"),
    ],
)
def test_denial_diagnostics_reject_wrong_scope_extra_fields_and_unbounded_labels(
    denied_server, changed
):
    with pytest.raises((ValueError, Fault)):
        denied_server.dispatch("executor", "root#1", dict(denial(), **changed))
    assert not denied_server.reports and not denied_server.disabled_mutations


def test_context_cannot_use_executor_denial_channel(denied_server):
    with pytest.raises(ValueError, match="role differs"):
        denied_server.dispatch("context", None, denial())
    assert not denied_server.reports and not denied_server.disabled_mutations


def test_denial_diagnostics_remain_bounded_and_fail_closed(denied_server):
    denied_server.disabled_mutations = {("root#1", "OP_" + str(i)) for i in range(128)}
    with pytest.raises(ValueError, match="capacity reached"):
        denied_server.dispatch("executor", "root#1", denial())
    assert len(denied_server.disabled_mutations) == 128 and not denied_server.reports


@pytest.fixture
def native_module():
    spec = importlib.util.spec_from_file_location(
        "native_closed_mutation_test", ROOT / "host_runtime/python/native.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("candidate", [True, False])
def test_candidate_teardown_uses_host_process_control_and_retains_legacy_default(
    native_module, candidate, monkeypatch
):
    events = []
    session = native_module.NativeSession.__new__(native_module.NativeSession)
    session.native_home = Path("/candidate") if candidate else None
    session.opened = True
    session.request = lambda *args, **kwargs: events.append(("request", args))
    session.context = SimpleNamespace(
        exchange=lambda *args: events.append(("context", args)),
        close=lambda: events.append(("context-close",)),
    )
    session.listener = SimpleNamespace(
        exchange=lambda *args: events.append(("listener", args)),
        close=lambda: events.append(("listener-close",)),
    )
    session.process = SimpleNamespace(
        pid=999999,
        poll=lambda: None,
        terminate=lambda: events.append(("terminate",)),
        wait=lambda **kwargs: 0,
    )
    session.log = None
    session.directory = SimpleNamespace(cleanup=lambda: events.append(("cleanup",)))
    monkeypatch.setattr(
        native_module.os, "killpg", lambda *args: events.append(("host-kill-group",))
    )
    session.close()
    requests = [event for event in events if event[0] in {"request", "context", "listener"}]
    assert (not requests) if candidate else requests
    assert ("host-kill-group",) in events and ("cleanup",) in events
    assert session.process is None
