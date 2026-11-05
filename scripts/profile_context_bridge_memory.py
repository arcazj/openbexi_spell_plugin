"""Full original 300-second workload with sampled Context/bridge allocation and ASan counters.

Diagnostic only: preserve original deadlines, sanitizers, accounting and audit writes.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qualify_v08_memory_comparison as comparison

# Diagnostic-only sampled byte ranking and read-only ASan retention counters.
import hashlib

original_prepare = comparison.prepare_overlay


def observed_prepare(workspace, profile, seconds):
    manifest = original_prepare(workspace, profile, seconds)
    relative = "host_runtime/native/allocation_trace.H"
    path = workspace / relative
    before = path.read_bytes()
    text = before.decode()
    anchor = "if (site.count<=selected[i].count) continue;"
    assert text.count(anchor) == 1
    text = text.replace(anchor, "if (site.bytes<=selected[i].bytes) continue;")
    anchor = "    char line[4096];"
    assert text.count(anchor) == 1
    text = text.replace(
        anchor, "\n".join(["    v08_alloc::v08_asan_stats(tick);", anchor])
    )
    anchor = 'extern "C" void v08_allocation_profile_dump(uint64_t tick) noexcept'
    assert text.count(anchor) == 1
    text = text.replace(
        anchor,
        'extern "C" void __asan_print_accumulated_stats();\nnamespace v08_alloc {\nvoid v08_asan_stats(uint64_t tick) {\n    std::fprintf(stderr,"V08_ASAN_STATS_BEGIN pid=%ld tick=%llu\\n",static_cast<long>(getpid()),static_cast<unsigned long long>(tick));\n    __asan_print_accumulated_stats();\n    std::fprintf(stderr,"V08_ASAN_STATS_END pid=%ld tick=%llu\\n",static_cast<long>(getpid()),static_cast<unsigned long long>(tick));\n}\n}\n'
        + anchor,
    )
    text = text.replace(
        "static Site sites[capacity];",
        "static Site sites[capacity];\nstatic uint64_t previousSiteBytes[capacity]{};",
    )
    text = text.replace(
        "    for (const auto& site:sites) {\n        sampled+=site.count;",
        "    uint64_t selectedBytes[top]{};\n    for (size_t index=0;index<capacity;++index) {\n        const auto& site=sites[index];\n        const auto freshBytes=site.bytes-previousSiteBytes[index];\n        previousSiteBytes[index]=site.bytes;\n        sampled+=site.count;",
    )
    text = text.replace(
        "if (site.bytes<=selected[i].bytes) continue;",
        "if (freshBytes<=selectedBytes[i]) continue;",
    )
    text = text.replace(
        "for (size_t j=top-1;j>i;--j) selected[j]=selected[j-1];",
        "for (size_t j=top-1;j>i;--j) { selected[j]=selected[j-1]; selectedBytes[j]=selectedBytes[j-1]; }",
    )
    text = text.replace(
        "selected[i]=site; break;",
        "selected[i]=site; selectedBytes[i]=freshBytes; break;",
    )
    assert "previousSiteBytes[index]=site.bytes" in text
    after = text.encode()
    path.write_bytes(after)
    manifest[relative] = dict(
        before_sha256=hashlib.sha256(before).hexdigest(),
        after_sha256=hashlib.sha256(after).hexdigest(),
        diagnostic_only=True,
    )
    relative = "host_runtime/native/private_bridge.cpp"
    path = workspace / relative
    before = path.read_bytes()
    assert (
        hashlib.sha256(before).hexdigest()
        == "0625fa8196b2981fb23857f1467b60912befff81027231b5bcd3b48ca636b4bf"
    )
    text = before.decode()
    anchor = "int main(int argc,char** argv) {\n    if (argc!=2) return 2;"
    assert text.count(anchor) == 1
    text = text.replace(
        anchor,
        'extern "C" bool v08_allocation_profile_start() noexcept;\n'
        + anchor
        + "\n    if (!v08_allocation_profile_start()) return 2;",
    )
    after = text.encode()
    path.write_bytes(after)
    manifest[relative] = dict(
        before_sha256=hashlib.sha256(before).hexdigest(),
        after_sha256=hashlib.sha256(after).hexdigest(),
        diagnostic_only=True,
    )
    relative = "scripts/v08_resource_probe.py"
    path = workspace / relative
    before = path.read_bytes()
    text = before.decode()
    anchor = '    result["native_allocator"] = []'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '    result["native_asan_statistics"] = []\n' + anchor)
    anchor = '                result["native_allocator"].extend(allocator_records(raw))'
    assert text.count(anchor) == 1
    text = text.replace(
        anchor,
        anchor
        + '\n                result["native_asan_statistics"].extend(asan_statistics(raw, original_pids))',
    )
    anchor = "@contextmanager\ndef observe("
    assert text.count(anchor) == 1
    observer = r"""def asan_statistics(raw, original_pids):
    # Diagnostic overlay only: retain bounded, complete, explicitly delimited
    # allocator statistics, never an arbitrary tail of the native log.
    pattern = rb"V08_ASAN_STATS_BEGIN pid=(\d+) tick=(\d+)\n(.*?)V08_ASAN_STATS_END pid=\1 tick=\2"
    latest = {}
    for match in re.finditer(pattern, raw, re.S):
        pid, tick = int(match[1]), int(match[2])
        if pid not in original_pids:
            continue
        body = match[3]
        if len(body) > 16384:
            raise ValueError("ASan diagnostic statistics exceeded bound")
        latest[pid] = dict(pid=pid, tick=tick,
            interleaved=b'V08_ASAN_STATS_BEGIN' in body,
            text=body.decode('ascii', errors='replace'))
    return list(latest.values())


"""
    text = text.replace(anchor, observer + anchor)
    after = text.encode()
    path.write_bytes(after)
    entry = manifest.setdefault(
        relative, dict(before_sha256=hashlib.sha256(before).hexdigest())
    )
    entry.update(
        after_sha256=hashlib.sha256(after).hexdigest(),
        diagnostic_only=True,
        diagnostic_note="Retain complete bounded ASan retention counters in addition to unchanged original memory fields",
    )
    return manifest


comparison.prepare_overlay = observed_prepare

original_run_child = comparison.run_child


def provisioned_child(command, cwd, log, timeout):
    if len(command) != 3 or Path(command[1]).name != "qualify_v08_native_launch.py":
        raise ValueError("Unexpected comparison child")
    return original_run_child(
        [*command, "--native-allocation-diagnostics"], cwd, log, timeout
    )


comparison.run_child = provisioned_child
if __name__ == "__main__":
    raise SystemExit(comparison.main())
