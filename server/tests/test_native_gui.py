"""Private native GUI bootstrap, immutable connection identity and denied paths."""

from concurrent.futures import ThreadPoolExecutor
import ast
import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace
import zipfile

import pytest

import test_child_gate as gates
from native_bridge_test_support import peer
from openbexi_spell_server.contracts import Fault

module = gates.module
ROOT = Path(__file__).resolve().parents[2]


def test_compiled_context_denial_survives_original_bridge_fields(tmp_path):
    """Execute the generated denial branch, then the real Python bridge reader.

    The C++ message/response shells isolate field construction, not native IPC.
    Field names come from the immutable upstream headers used by build_bridge;
    hosted original Context/bridge controls remain mandatory.
    """
    tree = ast.parse((ROOT / "host_runtime/build_admission_context.py").read_text())
    snippets = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and 'createErrorResponse("RSP_V08_GUI_DENIED"' in node.value
    ]
    assert len(snippets) == 1
    snippet = snippets[0]
    branch = snippet[
        snippet.index("        SPELLipcMessage response = SPELLipcHelper::createErrorResponse(") :
    ]
    branch = branch[: branch.index("return response;") + len("return response;")]
    fields, declarations = set(), []
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as bundle:
        for name in bundle.namelist():
            if name.startswith("include/SPELL_IPC/") and name.endswith(".H"):
                header = bundle.read(name).decode()
                fields.update(re.findall(r'FIELD_\w+\s*\(\s*"([^"]+)"\s*\)', header))
                if name.endswith("/SPELLipc.H"):
                    declarations = re.findall(
                        r'static const std::string FIELD_(?:ERROR|REASON|FATAL)\("[^"]+"\);',
                        header,
                    )
    assert len(declarations) == 3
    source = tmp_path / "denial.cpp"
    source.write_text(
        "#include <map>\n#include <string>\n#include <iostream>\n"
        "namespace MessageField {" + "\n".join(declarations) + "}\n"
        'namespace PythonConstants { const std::string False = "False"; }\n'
        "struct SPELLipcMessage {\n"
        "std::map<std::string,std::string> fields;\n"
        "void set(std::string key, std::string value) {fields[key]=value;}\n};\n"
        "namespace SPELLipcHelper {\n"
        "SPELLipcMessage createErrorResponse(std::string, const SPELLipcMessage&) {return {};}\n}\n"
        "SPELLipcMessage denied(const SPELLipcMessage& msg) {\n" + branch + "\n}\nint main() {\n"
        'for (const auto& field: denied({}).fields) std::cout << field.first << "=" << field.second << "\\n";\n}\n'
    )
    binary = tmp_path / "denial"
    subprocess.run(
        ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(binary)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    output = subprocess.check_output([str(binary)], text=True, timeout=5)
    emitted = dict(line.split("=", 1) for line in output.splitlines())
    # The frozen native bridge forwards only FIELD_* names; unlisted literals
    # disappear even though the Context correctly rejected the operation.
    forwarded = {key: value for key, value in emitted.items() if key in fields}
    # Exercise the full Python Bridge with real pipes. The C++ fixture above
    # still checks the original immutable error-field constants independently.
    response = json.dumps(dict(ok=False, message=dict(fields=forwarded)))
    script = (
        "for line in sys.stdin:\n"
        "    request = json.loads(line)\n"
        f"    response = json.loads({response!r})\n"
        "    response['seq'] = request['seq']\n"
        "    print(json.dumps(response), flush=True)\n"
    )
    with peer(script) as (bridge, _):
        with pytest.raises(RuntimeError, match="V08_CONTEXT_MUTATION_DENIED"):
            bridge.exchange("REQ_GUI_LOGIN", "CTX", {"Host": "copied"})
        assert not bridge.failed.is_set()
    assert forwarded == {
        "ErrorMsg": "V08_CONTEXT_MUTATION_DENIED",
        "ErrorReason": "Native Context GUI admission unavailable or rejected",
        "FatalError": "False",
    }


@pytest.fixture
def gui(monkeypatch):
    checks, reports = [], []
    gate = SimpleNamespace(
        root_instance="root#1", root_arguments="{}", root_check=lambda: checks.append(True)
    )
    gui = module.NativeGuiBinding(
        gate, lambda *_: 42, lambda event, **body: reports.append((event, body))
    )
    gui.key, gui.handle, gui.attempted = 1, 42, True
    gui.checks, gui.reports = checks, reports
    monkeypatch.setattr(module.select, "select", lambda *_: ([], [], []))
    return gui


def frame(operation="REQ_GUI_LOGIN", fields=None, **changes):
    return dict(
        schema="openbexi.native-gui/1",
        key=1,
        operation=operation,
        request=True,
        fields={"Host": "openbexi-host-v1"} if fields is None else fields,
        **changes,
    )


def root_open(**changes):
    fields = dict(
        ProcId="root#1",
        GuiMode="CONTROL",
        Arguments="{}",
        OpenMode="{Automatic:True,Visible:True,Blocking:False}",
    )
    fields.update(changes)
    return frame("REQ_OPEN_EXEC", fields)


def test_only_original_login_and_exact_root_can_mutate_bootstrap(gui):
    gui.admit(frame())
    gui.admit(root_open())
    assert len(gui.checks) == 2 and gui.logged_in and gui.open_attempted
    for body in (frame(), root_open()):
        with pytest.raises(ValueError, match="operation denied"):
            gui.admit(body)
    assert len(gui.checks) == 2


@pytest.mark.parametrize(
    "operation",
    [
        "REQ_GUI_LOGIN",
        "REQ_GUI_LOGOUT",
        "REQ_OPEN_EXEC",
        "REQ_CLOSE_EXEC",
        "REQ_KILL_EXEC",
        "REQ_ATTACH_EXEC",
        "REQ_DETACH_EXEC",
        "REQ_RECOVER_EXEC",
        "REQ_DELETE_RECOVERY",
        "REQ_REMOVE_CONTROL",
        "REQ_SET_BACKGROUND",
        "REQ_SET_SHARED_DATA",
        "REQ_DEL_SHARED_DATA",
        "REQ_ADD_SHARED_DATA_SCOPE",
        "REQ_DEL_SHARED_DATA_SCOPE",
        "REQ_SET_CTX_EXEC_DFLT",
        "REQ_INSTANCE_ID",
        "REQ_FUTURE_UNREVIEWED",
    ],
)
def test_management_rejected_without_changing_owner_bootstrap_or_running_authority(gui, operation):
    gui.admit(frame())
    gui.admit(root_open())
    with pytest.raises(ValueError, match="operation denied"):
        gui.admit(frame(operation, {}))
    assert len(gui.checks) == 2 and operation in gui.denied


@pytest.mark.parametrize(
    "changes",
    [
        dict(ProcId="child#1"),
        dict(Arguments="{'stolen': True}"),
        dict(GuiMode="BACKGROUND"),
        dict(OpenMode="{Automatic:True,Visible:False,Blocking:False}"),
        dict(SprocId="child#1"),
        dict(Condition="True"),
        dict(ParentId="other#1"),
        dict(GroupId="other#1"),
    ],
)
def test_root_bootstrap_rejects_modified_model_before_any_native_handler_and_never_retries(
    gui, changes
):
    gui.admit(frame())
    with pytest.raises(ValueError, match="operation denied"):
        gui.admit(root_open(**changes))
    with pytest.raises(ValueError, match="operation denied"):
        gui.admit(root_open())
    assert len(gui.checks) == 1


@pytest.mark.parametrize("key", [2, 0, -1, True])
def test_foreign_or_forged_key_cannot_login_read_or_open(gui, key):
    for body in (frame(), frame("REQ_CLIENT_INFO", {}), root_open()):
        with pytest.raises((ValueError, Fault)):
            gui.admit(dict(body, key=key))
    assert not gui.logged_in and not gui.open_attempted and not gui.checks


def test_rpc_loss_retires_login_or_root_attempt_without_authorizing_replay(gui):
    gui.admit(frame())

    def lost():
        raise TimeoutError("Reply lost after authority check")

    gui.gate.root_check = lost
    with pytest.raises(TimeoutError):
        gui.admit(root_open())
    with pytest.raises(ValueError):
        gui.admit(root_open())
    assert gui.open_attempted


def test_concurrent_root_open_has_only_one_initial_authority_check(gui):
    gui.admit(frame())

    def attempt(_):
        try:
            gui.admit(root_open())
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(20))) == 1
    assert len(gui.checks) == 2


def test_bridge_death_denies_reads_commands_and_management_without_rebinding(gui, monkeypatch):
    gui.admit(frame())
    monkeypatch.setattr(module.select, "select", lambda handles, *_: (handles, [], []))
    for body in (
        root_open(),
        frame("REQ_EXEC_INFO", {}),
        dict(frame("CMD_RUN", {}), request=False),
    ):
        with pytest.raises(ValueError):
            gui.admit(body)
    with pytest.raises(ValueError, match="already attempted"):
        gui.bind(2, SimpleNamespace())
    assert len(gui.checks) == 1


def test_read_and_existing_executor_gates_remain_separate_from_management(gui):
    gui.admit(frame())
    for operation in gui.READS | gui.CLOSED_EXECUTOR_REQUESTS:
        gui.admit(frame(operation, {}))
    for operation in gui.EXECUTOR_MESSAGES:
        gui.admit(dict(frame(operation, {}), request=False))
    assert len(gui.checks) == 1 and not gui.open_attempted


def test_executor_cannot_impersonate_native_context_gui_callback(gui):
    server = module.NativeAdmissionServer.__new__(module.NativeAdmissionServer)
    server.gui = gui
    with pytest.raises(ValueError, match="scope denied"):
        server.dispatch("executor", "root#1", frame())
    assert not gui.logged_in


@pytest.mark.parametrize("failure", [None, "key", "dead", "writable", "pin"])
def test_binding_is_protected_one_shot_original_readonly_bridge(gui, monkeypatch, failure):
    gui.attempted, gui.key, gui.handle = False, None, None
    executable = Path("/bridge/spell-host-ipc")
    monkeypatch.setattr(module, "Path", lambda _: SimpleNamespace(resolve=lambda **_: executable))
    monkeypatch.setattr(
        module.os,
        "statvfs",
        lambda _: SimpleNamespace(f_flag=0 if failure == "writable" else module.os.ST_RDONLY),
    )
    pins = []

    def pin(*identity):
        pins.append(identity)
        if failure == "pin":
            raise ValueError("Original bridge PID changed during binding")
        return 42

    gui.pin_process = pin
    process = SimpleNamespace(pid=1234, poll=lambda: 0 if failure == "dead" else None)
    if failure is None:
        gui.bind(1, process)
        assert gui.key == 1 and gui.handle == 42
        assert pins == [(1234, module.os.getpid(), executable)]
    else:
        with pytest.raises(ValueError):
            gui.bind(True if failure == "key" else 1, process)
        assert gui.key is None and gui.handle is None
    with pytest.raises(ValueError, match="already attempted"):
        gui.bind(2, process)


@pytest.mark.parametrize(
    "operation",
    [
        "MSG_ADD_CLIENT",
        "MSG_REMOVE_CLIENT",
        "MSG_BACKGROUND",
        "MSG_SHOW_NODE_DEPTH",
        "MSG_WVARIABLES_ENABLE",
        "MSG_WVARIABLES_DISABLE",
        "MSG_DRESOURCES_ENABLE",
        "MSG_DRESOURCES_DISABLE",
        "MSG_FUTURE_UNREVIEWED",
    ],
)
def test_external_roster_and_direct_state_messages_never_reach_native_client_handler(
    gui, operation
):
    gui.admit(frame())
    with pytest.raises(ValueError):
        gui.admit(dict(frame(operation, {}), request=False))
    assert operation in gui.denied


def test_compiled_transport_never_accepts_proposed_reused_or_exhausted_keys(tmp_path):
    source = tmp_path / "gui.cpp"
    source.write_text(r"""
#include "gui_policy.H"
#include <cassert>
int main() {
    int last = 0;
    for (int i = 1; i <= 1024; ++i) {
        assert(v08_next_gui_key(last, 0) == i);
        for (int proposed: {1, i, -1, 65535}) {
            bool denied = false;
            try { v08_next_gui_key(last, proposed); }
            catch (const std::runtime_error&) { denied = true; }
            assert(denied && last == i);
        }
    }
    bool denied = false;
    try { v08_next_gui_key(last, 0); }
    catch (const std::runtime_error&) { denied = true; }
    assert(denied && last == 1024);
}
""")
    binary = tmp_path / "gui"
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
