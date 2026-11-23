"""Compile the four measured, upstream Context log expressions before and after composition."""

import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "native_builder", ROOT / "host_runtime/build_admission_context.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


GETTERS = (
    "exec->getModel().getParentInstanceId()",
    "SPELLdataHelper::executorStatusToString(st)",
    "exec->getModel().getAsRunFilename()",
    "SPELLdataHelper::openModeToString(exec->getModel().getOpenMode())",
)


def frozen():
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        return archive.read("lib/SPELL_CTX/src/SPELLexecutorManager.C").decode()


def test_executor_info_change_preserves_complete_log_locations_and_rejects_drift():
    original = frozen()
    candidate = builder.reuse_executor_info_log_line(original)
    before = original.splitlines()
    after = candidate.splitlines()
    assert len(before) == len(after)
    changed = [(a, b) for a, b in zip(before, after, strict=True) if a != b]
    assert len(changed) == 7
    assert [a for a, b in changed if "infoLogStorage" in b] == ["", ""]
    for getter in GETTERS:
        assert sum(getter in a and getter in b for a, b in changed) == 1
    for source in (original.replace("ASRUN file        : ", "new ASRUN label"), candidate):
        with pytest.raises(ValueError, match="preimage differs"):
            builder.reuse_executor_info_log_line(source)


def log_function(name, source):
    body = []
    for full_line in source.splitlines():
        line = full_line.strip()
        if "infoLogStorage" in line:
            body.append(line)
        for i, getter in enumerate(GETTERS):
            if line.startswith("LOG_INFO(") and getter in line:
                body.append(line.replace(getter, f"get({i})"))
    assert len(body) == (4 if name == "before" else 6)
    return "void " + name + "() {\n" + "\n".join(body) + "\n}\n"


def test_executor_info_reduces_allocations_with_identical_log_bytes_and_getter_calls(tmp_path):
    original = frozen()
    candidate = builder.reuse_executor_info_log_line(original)
    source = tmp_path / "executor-info.cpp"
    source.write_text(
        r"""#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>
#include "line_stack.H"
static bool measuring=false;
static std::uint64_t calls=0, bytes=0;
extern "C" void __sanitizer_malloc_hook(const volatile void*,size_t size) {
    if(measuring) { ++calls; bytes+=size; }
}
std::array<std::string,4> values;
std::array<unsigned,4> reads;
std::vector<std::string> captured;
unsigned nested=0;
void (*reenter)()=nullptr;
std::string get(size_t index) { ++reads[index]; return values[index]; }
void LOG_INFO(const std::string& value) {
    if(nested) { --nested; auto held=value; reenter(); assert(held==value); }
    if(!measuring) captured.push_back(value);
}
"""
        + log_function("before", original)
        + log_function("after", candidate)
        + r"""
int main() {
    for(const size_t size : {0, 15, 16, 127, 8192}) {
        for(size_t i=0;i<values.size(); ++i) values[i]=std::string(size,char('a'+i))+std::string("\0Z",2);
        reads={}; captured.clear(); before(); auto expected=captured; auto expectedReads=reads;
        reads={}; captured.clear(); after(); assert(expected==captured && expectedReads==reads);
        assert(expected.size()==4 && std::all_of(reads.begin(),reads.end(),[](unsigned n){return n==1;}));
    }
    captured.clear(); nested=10; reenter=before; before(); auto recursive=captured;
    captured.clear(); nested=10; reenter=after; after(); assert(captured==recursive);
    values={"", "RUNNING", "/workspace/asrun/example/procedure.asrun", "CONTROL"};
    for(auto emit : {before,after}) {
        calls=bytes=0; measuring=true;
        for(unsigned i=0;i<10000;++i) emit();
        measuring=false;
        std::printf("%llu %llu\n",(unsigned long long)calls,(unsigned long long)bytes);
    }
}
"""
    )
    binary = tmp_path / "executor-info"
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-O1",
            "-g1",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
            "-no-pie",
            "-I" + str(ROOT / "host_runtime/native"),
            str(source),
            "-o",
            str(binary),
        ],
        check=True,
        timeout=60,
    )
    output = subprocess.check_output([binary], text=True, timeout=30)
    before, after = [
        dict(zip(("allocations", "bytes"), map(int, row.split()), strict=True))
        for row in output.splitlines()
    ]
    assert 0 < after["allocations"] < before["allocations"]
    assert 0 < after["bytes"] < before["bytes"]
    print(
        json.dumps(
            {
                "scope": "four log expressions, 10000 calls per expression",
                "before": before,
                "after": after,
            }
        )
    )
