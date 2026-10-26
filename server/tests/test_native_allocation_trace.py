"""Actual ASan hooks remain opt-in, bounded, concurrent and non-recursive."""

import os
import importlib.util
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("shared", [False, True])
def test_compiled_allocation_sampler_is_bounded_and_opt_in(tmp_path, shared):
    source, binary = tmp_path / "trace.cpp", tmp_path / "trace"
    source.write_text("""
#include "allocation_trace.H"
#include <thread>
#include <string>
#include <vector>
int main() {
    if(!v08_allocation_profile_start())return 2;
    std::vector<std::thread> workers;
    for(int t=0;t<4;t++)workers.emplace_back([]{
        for(int i=0;i<20000;i++){
            auto* data=new char[64+i%4096];
            data[0]='x'; asm volatile("" : : "r"(data) : "memory"); delete[] data;
        }
    });
    for(auto& worker:workers)worker.join();
    for(uint64_t t=1;t<=20000;t++)v08_allocation_profile_dump(t*1000000);
}
""")
    flags = [
        "c++",
        "-std=c++17",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-O1",
        "-g",
        "-pthread",
        "-fsanitize=address,undefined",
        "-fno-sanitize-recover=all",
        "-fno-omit-frame-pointer",
        "-no-pie",
        "-I",
        str(ROOT / "host_runtime/native"),
    ]
    objects = []
    if shared:
        module = tmp_path / "module.cpp"
        library = tmp_path / "libtrace.so"
        module.write_text('#include "allocation_trace.H"\n')
        source.write_text(
            source.read_text().replace(
                '#include "allocation_trace.H"',
                '#include <cstdint>\nextern "C" bool v08_allocation_profile_start() noexcept;\n'
                'extern "C" void v08_allocation_profile_dump(uint64_t) noexcept;',
            )
        )
        subprocess.run(
            flags + ["-shared", "-fPIC", str(module), "-o", str(library)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        objects.append(str(library))
    subprocess.run(
        flags + [str(source), *objects, "-o", str(binary)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    env = dict(
        os.environ, ASAN_OPTIONS="detect_leaks=0:abort_on_error=1", UBSAN_OPTIONS="halt_on_error=1"
    )
    for enabled in (False, True):
        # Numeric resource observation alone must not enable expensive stacks.
        env["OPENBEXI_V08_RESOURCE_DIAGNOSTICS"] = "1"
        env["OPENBEXI_V08_ALLOCATION_DIAGNOSTICS"] = "1" if enabled else "0"
        result = subprocess.run(
            [str(binary), *(["enabled"] if enabled else [])],
            env=env,
            capture_output=True,
            check=True,
            timeout=30,
        )
        assert not result.stdout
        if not enabled:
            assert not result.stderr
            continue
        lines = result.stderr.decode().splitlines()
        totals = [line for line in lines if line.startswith("V08_ALLOC ")]
        sites = [line for line in lines if line.startswith("V08_ALLOC_SITE ")]
        assert len(totals) == 2
        assert 1 <= len(sites) <= 12
        assert len(lines) == len(totals) + len(sites)
        assert all(len(line) < 4096 for line in lines)
        counts = [dict(re.findall(r"(calls|bytes|samples|skipped)=(\d+)", line)) for line in totals]
        assert int(counts[0]["calls"]) >= 80000
        assert int(counts[0]["bytes"]) > 100000000
        assert 50 < int(counts[0]["samples"]) < 1000
        assert counts[0] == counts[1], "Reporting must not sample its own allocations"
        spec = importlib.util.spec_from_file_location(
            "trace_collector", ROOT / "scripts/v08_resource_probe.py"
        )
        collector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(collector)
        captured = collector.allocation_profiles(result.stderr)
        assert len(captured) == 1
        assert captured[0]["calls"] == int(counts[-1]["calls"])
        assert captured[0]["sites"], "The host collector must retain actual compiled stack samples"
