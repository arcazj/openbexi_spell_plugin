"""Compare exact legacy formatting and record bytes with owned bounded reuse."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def timestamp_source(tmp_path_factory):
    folder = tmp_path_factory.mktemp("native-timestamps")
    archive = ROOT / "docs/reference/SPELL2.6.10-src.zip"
    source = folder / "source"
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(source)
    saved = sys.path[:]
    try:
        sys.path[:0] = [str(ROOT / "source_port"), str(ROOT / "host_runtime")]
        from native_patches import apply_tree
        from integrated_patches import apply_native_tree

        apply_tree(source)
        apply_native_tree(source, archive, folder / "composition")
    finally:
        sys.path[:] = saved
    before = (source / "lib/SPELL_CIF/src/SPELLasRun.C").read_text()
    spec = importlib.util.spec_from_file_location(
        "timestamp_builder", ROOT / "host_runtime/build_admission_context.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.reuse_native_timestamp_and_asrun(source)
    return source, before, builder


def extract(text, signature):
    start = text.index(signature)
    return text[start : text.index("\n}", start) + 2]


def test_compiled_timestamp_and_asrun_bytes_concurrency_and_churn(timestamp_source, tmp_path):
    source, before, _ = timestamp_source
    with zipfile.ZipFile(ROOT / "docs/reference/SPELL2.6.10-src.zip") as archive:
        utils = archive.read("lib/SPELL_UTIL/src/SPELLutils.C").decode()
    original = extract(utils, "std::string SPELLutils::timestamp()")
    original = original.replace("SPELLutils::timestamp()", "legacy_timestamp()")
    (tmp_path / "legacy.inc").write_text(original)
    after = (source / "lib/SPELL_CIF/src/SPELLasRun.C").read_text()
    (tmp_path / "records.inc").write_text(
        extract(before, "void SPELLasRun::toAsRun(").replace("SPELLasRun::", "Before::")
        + "\n"
        + extract(after, "void SPELLasRun::toAsRun(").replace("SPELLasRun::", "After::")
    )
    (tmp_path / "main.cpp").write_text("""
#include <atomic>
#include <cassert>
#include <climits>
#include <fstream>
#include <iostream>
#include <mutex>
#include <pthread.h>
#include <string>
#include <thread>
#include <vector>
#define TIME_FORMAT_DEFAULT 9
#define TIME_FORMAT_SLASH 1
#define TIME_FORMAT_DOT 0
#define ISTR(x) std::to_string(x)
struct SPELLdateDesc {int year,month,day,yday,hours,minutes,seconds;};
static SPELLdateDesc observed{2026,10,27,300,12,34,56};
static int s_timeFormat=TIME_FORMAT_DEFAULT;
static SPELLdateDesc getSystemDate(){return observed;}
#include "timestamp_format.H"
static std::atomic<bool> cancel_format{false},format_entered{false},fail_format{false};
namespace SPELLutils {
    static void timestamp(std::string& out){
        if(fail_format.exchange(false))throw std::bad_alloc();
        if(cancel_format.load()) {
            format_entered=true;
            for(;;)pthread_testcancel();
        }
        v08_format_timestamp(out,observed,s_timeFormat);
    }
    static std::string timestamp(){std::string out;timestamp(out);return out;}
}
#include "legacy.inc"
static std::atomic<bool> measuring{false};
static std::atomic<size_t> allocations{0};
extern "C" void __sanitizer_malloc_hook(const volatile void*,size_t){if(measuring)++allocations;}
struct Before {
    std::ofstream m_file;unsigned long m_sequence=0;
    explicit Before(const std::string& path):m_file(path){}
    void toAsRun(const std::string&,bool);
};
struct After {
    std::ofstream m_file;unsigned long m_sequence=0;
    std::recursive_mutex m_v08RecordMutex;std::string m_v08Record;
    explicit After(const std::string& path):m_file(path){}
    void toAsRun(const std::string&,bool);
};
#include "records.inc"
int main(int argc,char**argv){
    if(argc!=2)return 2;
    unsigned cases=0;
    for(int format:{TIME_FORMAT_DEFAULT,TIME_FORMAT_SLASH,TIME_FORMAT_DOT,-5,99}) {
        s_timeFormat=format;
        for(int value:{INT_MIN,-99,-9,-1,0,1,9,10,99,100,366,1900,9999,INT_MAX}) {
            observed={value,value,value,value,value,value,value};
            std::string actual;SPELLutils::timestamp(actual);
            assert(actual==legacy_timestamp());++cases;
        }
    }
    observed={2026,10,27,300,12,34,56};s_timeFormat=TIME_FORMAT_DEFAULT;
    std::string target;target.reserve(128);
    allocations=0;measuring=true;
    for(int i=0;i<10000;++i)SPELLutils::timestamp(target);
    measuring=false;const auto formatted=allocations.load();assert(formatted==0);
    Before before(std::string(argv[1])+"/before.ASRUN");
    After after(std::string(argv[1])+"/after.ASRUN");
    const std::string info="LINE\\t\\troot:123/7";
    before.toAsRun(info,true);after.toAsRun(info,true);
    allocations=0;measuring=true;
    for(int i=0;i<10000;++i)before.toAsRun(info,true);
    measuring=false;const auto oldCount=allocations.load();
    allocations=0;measuring=true;
    for(int i=0;i<10000;++i)after.toAsRun(info,true);
    measuring=false;const auto newCount=allocations.load();
    assert(oldCount>=20000 && newCount==0);
    after.toAsRun(std::string(1000000,'x'),true);
    assert(after.m_v08Record.capacity()<=1024);
    After concurrent(std::string(argv[1])+"/concurrent.ASRUN");
    std::vector<std::thread> workers;
    for(int t=0;t<4;++t)workers.emplace_back([&,t]{
        const std::string record="LINE\\t\\tthread:"+std::to_string(t);
        for(int n=0;n<200;++n)concurrent.toAsRun(record,true);
    });
    for(auto&worker:workers)worker.join();
    fail_format=true;
    try{concurrent.toAsRun("FAILED_ALLOCATION",true);assert(false);}catch(const std::bad_alloc&){}
    cancel_format=true;
    std::thread cancelled([&]{concurrent.toAsRun("CANCELLED",true);});
    while(!format_entered.load())std::this_thread::yield();
    assert(pthread_cancel(cancelled.native_handle())==0);cancelled.join();
    cancel_format=false;
    concurrent.toAsRun("SURVIVOR",true);
    std::cout<<"{\\"cases\\":"<<cases<<",\\"timestamp_allocations\\":"<<formatted
             <<",\\"before_allocations\\":"<<oldCount<<",\\"after_allocations\\":"<<newCount<<"}\\n";
}
""")
    binary = tmp_path / "timestamp"
    built = subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-O1",
            "-g",
            "-pthread",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
            "-no-pie",
            "-I" + str(ROOT / "host_runtime/native"),
            "-I" + str(tmp_path),
            str(tmp_path / "main.cpp"),
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert built.returncode == 0, built.stderr
    result = subprocess.run(
        [str(binary), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
        env=dict(
            os.environ,
            ASAN_OPTIONS="detect_leaks=0:abort_on_error=1",
            UBSAN_OPTIONS="halt_on_error=1",
        ),
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["cases"] == 70
    before_bytes = (tmp_path / "before.ASRUN").read_bytes()
    assert (tmp_path / "after.ASRUN").read_bytes().startswith(before_bytes)
    lines = (tmp_path / "concurrent.ASRUN").read_text().splitlines()
    assert [int(line.split("\t")[1]) for line in lines] == list(range(801))
    assert lines[-1] == "2026-10-27 12:34:56\t800\tSURVIVOR"
    (tmp_path / "measurement.json").write_text(json.dumps(receipt, indent=2) + "\n")


def test_formatter_overlay_rejects_duplicate(timestamp_source):
    source, _, builder = timestamp_source
    with pytest.raises(ValueError, match="preimage differs"):
        builder.reuse_native_timestamp_and_asrun(source)
