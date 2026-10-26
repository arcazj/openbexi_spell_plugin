"""Actual ASan hooks remain opt-in, bounded, concurrent and non-recursive."""

import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_compiled_allocation_sampler_is_bounded_and_opt_in(tmp_path):
    source, binary = tmp_path / "trace.cpp", tmp_path / "trace"
    source.write_text("""
#include "allocation_trace.H"
#include <thread>
#include <string>
#include <vector>
int main(int argc,char**) {
    if(argc>1)v08_allocation_profile_enable();
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
    subprocess.run(
        [
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
            "-Wl,--export-dynamic",
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
    env = dict(
        os.environ, ASAN_OPTIONS="detect_leaks=0:abort_on_error=1", UBSAN_OPTIONS="halt_on_error=1"
    )
    for enabled in (False, True):
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
