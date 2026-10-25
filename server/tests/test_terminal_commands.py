"""Terminal owner grants and original CIF pre-effect boundary regressions."""

import importlib.util
from pathlib import Path
import shutil
import subprocess
import uuid

import pytest
import test_owner_commands as owner
import test_native_prompt_boundary as native_boundary

source = owner.source
native_sources = native_boundary.native_sources
setup = owner.setup
family = owner.family
queue = owner.queue
provider = owner.provider
agent = owner.agent
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def terminal(queue):
    queue.terminal = True
    return queue


@pytest.mark.parametrize("command", ["CMD_ABORT", "CMD_CLOSE"])
def test_terminal_profile_is_explicit(queue, family, pki, command):
    assert owner.enqueue(family, pki, command)[0] == 403
    assert not owner.rows(family)


@pytest.mark.parametrize("command", ["CMD_ABORT", "CMD_CLOSE"])
def test_terminal_fresh_owner_scope_and_single_use(terminal, family, pki, command):
    grant = owner.delivered(family, pki, command)
    assert owner.worker(family, pki, "command-consume", grant)[0] == 409
    assert owner.worker(family, pki, "command-forward", grant)[0] == 200
    assert owner.worker(family, pki, "command-consume", grant)[0] == 200
    assert owner.worker(family, pki, "command-consume", grant)[0] in (403, 409)
    assert terminal.terminal_pending(family["grant"].execution_id)
    assert owner.enqueue(family, pki, "CMD_RUN")[0] == 403
    assert owner.enqueue(family, pki, "CMD_STEP")[0] == 403
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


@pytest.mark.parametrize("command", ["CMD_ABORT", "CMD_CLOSE"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("token", "0" * 64),
        ("operation_digest", "0" * 64),
        ("member_binding_hash", "0" * 64),
        ("control_epoch", 7),
        ("owner", "bob"),
        ("execution_id", str(uuid.uuid4())),
        ("command", "CMD_RUN"),
        ("target_admission_id", str(uuid.uuid4())),
    ],
)
def test_terminal_final_consumption_rechecks_bound_identity(
    terminal, family, pki, command, field, value
):
    grant = owner.delivered(family, pki, command)
    assert owner.worker(family, pki, "command-forward", grant)[0] == 200
    assert owner.worker(family, pki, "command-consume", dict(grant, **{field: value}))[0] == 403
    assert owner.rows(family)[0]["state"] == "FORWARD_UNPROVEN"
    assert not terminal.terminal_pending(family["grant"].execution_id)


@pytest.mark.parametrize("command", ["CMD_ABORT", "CMD_CLOSE"])
def test_terminal_disconnect_at_final_cif_gate(terminal, family, pki, command):
    grant = owner.delivered(family, pki, command)
    assert owner.worker(family, pki, "command-forward", grant)[0] == 200
    family["controller"]("session.close", dict(connection_id=family["connection"]))
    assert owner.worker(family, pki, "command-consume", grant)[0] == 403
    assert owner.rows(family)[0]["state"] == "FORWARD_UNPROVEN"


def test_terminal_overlay_precedes_real_prompt_and_close_effects(native_sources, tmp_path):
    _, _, enabled, _ = native_sources
    root = tmp_path / "source"
    shutil.copytree(enabled, root)
    spec = importlib.util.spec_from_file_location(
        "terminal_patch", ROOT / "host_runtime/native_terminal_patch.py"
    )
    patcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patcher)
    patcher.patch_terminal_tree(root)
    text = (root / "lib/SPELL_CIFS/src/SPELLserverCif.C").read_text()
    body = text.split("void SPELLserverCif::processMessage(", 1)[1]
    assert body.index("v08_admit_terminal(") < body.index("cancelPrompt(nullptr,")
    assert body.index("v08_admit_terminal(") < body.index("setClosing();")
    assert body.index("v08_admit_terminal(") < body.index(".command(cmd, true)")
    with pytest.raises(ValueError, match="declaration differs"):
        patcher.patch_terminal_tree(root)


def test_compiled_terminal_single_use_and_lost_ack(tmp_path):
    for name in ("terminal_gate.H", "prompt_policy.H"):
        shutil.copyfile(ROOT / "host_runtime/native" / name, tmp_path / name)
    (tmp_path / "admission_ipc.H").write_text("""#include <stdexcept>
#include <string>
#include <initializer_list>
#include <utility>
inline int calls=0;
inline bool lost=false;
inline void v08_native_request(std::initializer_list<std::pair<const char*,std::string>>) {
    ++calls; if (lost) throw std::runtime_error("lost acknowledgement");
}
""")
    source = tmp_path / "terminal.cpp"
    source.write_text("""#include "terminal_gate.H"
#include <cassert>
int main() {
 std::string a="00000000-0000-0000-0000-000000000001";
 std::string b="00000000-0000-0000-0000-000000000002";
 std::map<std::string,std::string> fields{{"ProcId","main#1"},{"V08ControlRequest",a}};
 assert(v08_terminal_valid("CMD_ABORT",true,fields,"main#1"));
 assert(!v08_terminal_valid("CMD_ABORT",false,fields,"main#1"));
 fields["ParentId"]="main#1";
 assert(!v08_terminal_valid("CMD_ABORT",true,fields,"main#1"));
 v08_admit_terminal("main#1",a,"CMD_ABORT");
 v08_take_terminal("main#1",a,"CMD_ABORT");
 try {v08_take_terminal("main#1",a,"CMD_ABORT");assert(false);} catch(const std::runtime_error&) {}
 try {v08_admit_terminal("main#1",a,"CMD_ABORT");assert(false);} catch(const std::runtime_error&) {}
 assert(calls==1); lost=true;
 try {v08_admit_terminal("main#1",b,"CMD_CLOSE");assert(false);} catch(const std::runtime_error&) {}
 lost=false;
 try {v08_admit_terminal("main#1",b,"CMD_CLOSE");assert(false);} catch(const std::runtime_error&) {}
 try {v08_take_terminal("main#1",b,"CMD_CLOSE");assert(false);} catch(const std::runtime_error&) {}
 assert(calls==2);
}
""")
    binary = tmp_path / "terminal"
    subprocess.run(
        ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(binary)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    subprocess.run([str(binary)], check=True, timeout=5)
