"""Compile the frozen and corrected spawn methods; exercise real Linux children."""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "spawn_patch", ROOT / "host_runtime/build_admission_context.py"
)
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)

HARNESS = r"""
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <pthread.h>
#include <signal.h>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>
static pthread_mutex_t blocked = PTHREAD_MUTEX_INITIALIZER;
static bool fail_spawn = false;
static int calls = 0;
static void child_callback() { pthread_mutex_lock(&blocked); }
extern "C" int __real_posix_spawn(pid_t*, const char*,
    const posix_spawn_file_actions_t*, const posix_spawnattr_t*, char* const[], char* const[]);
extern "C" int __wrap_posix_spawn(pid_t* pid, const char* path,
    const posix_spawn_file_actions_t* actions, const posix_spawnattr_t* attr,
    char* const argv[], char* const env[]) {
    ++calls;
    return fail_spawn ? EAGAIN : __real_posix_spawn(pid,path,actions,attr,argv,env);
}
int main(int argc, char** argv) {
    if (argc != 3) return 2;
    if (std::string(argv[1]) == "atfork") {
        pthread_mutex_lock(&blocked);
        if (pthread_atfork(nullptr,nullptr,child_callback)) return 3;
    }
    fail_spawn = std::string(argv[1]) == "fail";
    if (std::string(argv[1]) == "mask") {
        sigset_t mask;
        sigemptyset(&mask);
        sigaddset(&mask,SIGTERM);
        sigaddset(&mask,SIGUSR1);
        if (pthread_sigmask(SIG_BLOCK,&mask,nullptr)) return 5;
    }
    pid_t pid;
    try { pid = SPELLprocess::popen(argv[2]); }
    catch (const std::exception&) {
        std::cout << "{\"spawn_failed\":true,\"calls\":" << calls << "}" << std::endl;
        return 0;
    }
    if (std::string(argv[1]) == "mask") {
        sigset_t mask;
        if (pthread_sigmask(SIG_BLOCK,nullptr,&mask) ||
            !sigismember(&mask,SIGTERM) || !sigismember(&mask,SIGUSR1)) return 6;
    }
    int status=0;
    for (int n=0;n<200;++n) {
        if (waitpid(pid,&status,WNOHANG)==pid) {
            std::cout << "{\"exited\":true,\"parent\":" << getpid()
              << ",\"child\":" << pid << ",\"exit_code\":"
              << (WIFEXITED(status) ? WEXITSTATUS(status) : -WTERMSIG(status))
              << ",\"calls\":" << calls << "}" << std::endl;
            return 0;
        }
        usleep(5000);
    }
    kill(pid,SIGKILL);
    if (waitpid(pid,&status,0)!=pid) return 4;
    std::cout << "{\"exited\":false,\"reaped\":true}" << std::endl;
}
"""


@pytest.fixture(scope="session")
def spawn_binaries(tmp_path_factory):
    folder = tmp_path_factory.mktemp("native-spawn")
    include = folder / "SPELL_PRC"
    include.mkdir()
    (include / "SPELLprocessManager.H").write_text(
        "#include <string>\n#include <stdexcept>\n#include <sys/types.h>\n"
        "#define DEBUG(x) ((void)0)\n"
        "#define THROW_EXCEPTION(a,b,c) throw std::runtime_error(a)\n"
        "struct SPELLprocess { static pid_t popen(std::string); };\n"
    )
    original = (ROOT / "server/tests/native_spawn_legacy.cpp").read_text()
    binaries = {}
    for version, source in (
        ("before", original),
        ("after", patcher.replace_native_spawn(original)),
    ):
        path, binary = folder / (version + ".cpp"), folder / version
        # Headers precede the exact production method; append only the driver.
        split = HARNESS.index("int main(")
        path.write_text(HARNESS[:split] + source + HARNESS[split:])
        subprocess.run(
            [
                "c++",
                "-std=c++17",
                "-pthread",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I",
                str(folder),
                str(path),
                "-Wl,--wrap=posix_spawn",
                "-o",
                str(binary),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        binaries[version] = binary
    return binaries


def run(binary, mode, command, **options):
    result = subprocess.run(
        [str(binary), mode, command], capture_output=True, check=True, timeout=5, **options
    )
    assert not result.stderr
    return json.loads(result.stdout)


def test_spawn_avoids_inherited_fork_callback_deadlock(spawn_binaries):
    before = run(spawn_binaries["before"], "atfork", "exit 23")
    after = run(spawn_binaries["after"], "atfork", "exit 23")
    assert before == dict(exited=False, reaped=True)
    assert after["exited"] and after["exit_code"] == 23 and after["calls"] == 1
    if output := os.environ.get("OPENBEXI_SERVER_EVIDENCE_DIR"):
        (Path(output) / "native-spawn-regression.json").write_text(
            json.dumps(dict(before=before, after=after, historical_cause_established=False)) + "\n"
        )


@pytest.mark.parametrize("version", ["before", "after"])
def test_spawn_preserves_parent_environment_cwd_arguments_and_descriptor(
    spawn_binaries, tmp_path, version
):
    output = tmp_path / "child.json"
    descriptor = os.open(output, os.O_CREAT | os.O_WRONLY, 0o600)
    code = (
        "import os,json;os.write("
        + str(descriptor)
        + ",json.dumps({'pid':os.getpid(),'parent':os.getppid(),'cwd':os.getcwd(),"
        "'value':os.environ['OPENBEXI_SPAWN_MARK']}).encode())"
    )
    try:
        result = run(
            spawn_binaries[version],
            "plain",
            "exec " + shlex.quote(sys.executable) + " -c " + shlex.quote(code),
            cwd=tmp_path,
            env=dict(os.environ, OPENBEXI_SPAWN_MARK="space ' quote $ literal"),
            pass_fds=(descriptor,),
        )
    finally:
        os.close(descriptor)
    child = json.loads(output.read_text())
    assert result["exited"] and result["exit_code"] == 0
    assert child == dict(
        pid=result["child"],
        parent=result["parent"],
        cwd=str(tmp_path),
        value="space ' quote $ literal",
    )


@pytest.mark.parametrize("command,code", [("exit 23", 23), ("kill -TERM $$", -15)])
def test_spawn_preserves_exit_and_signal_status(spawn_binaries, command, code):
    assert run(spawn_binaries["after"], "plain", command)["exit_code"] == code


@pytest.mark.parametrize("version", ["before", "after"])
def test_spawn_preserves_port_signal_policy(spawn_binaries, tmp_path, version):
    output = tmp_path / "mask.json"
    code = (
        "import signal,json,pathlib;mask=signal.pthread_sigmask(signal.SIG_BLOCK,[]);"
        "pathlib.Path(" + repr(str(output)) + ").write_text(json.dumps("
        "{'term':signal.SIGTERM in mask,'user':signal.SIGUSR1 in mask}))"
    )
    result = run(
        spawn_binaries[version],
        "mask",
        "exec " + shlex.quote(sys.executable) + " -c " + shlex.quote(code),
    )
    assert result["exited"] and result["exit_code"] == 0
    assert json.loads(output.read_text()) == dict(term=False, user=True)


def test_spawn_error_is_explicit_and_never_retries(spawn_binaries):
    assert run(spawn_binaries["after"], "fail", "exit 0") == dict(spawn_failed=True, calls=1)


def test_spawn_patch_rejects_different_or_already_modified_sources():
    original = (ROOT / "server/tests/native_spawn_legacy.cpp").read_text()
    for changed in (
        original.replace("pid = fork();", "pid = vfork();"),
        patcher.replace_native_spawn(original),
    ):
        with pytest.raises(ValueError, match="spawn source differs"):
            patcher.replace_native_spawn(changed)
