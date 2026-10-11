# Native child, shared-data and scheduler qualification

Three additional procedures pass through the original server executor and CIF:

| Procedure | Independent result |
| --- | --- |
| Shared data | Set/read/update an integer, list keys, round-trip a list containing a boolean, float and Unicode string, then delete the keys |
| Parent/child | Start a real child with native ARGS containing 21, block until it completes, read its shared-data result 42, then close the parent and context normally |
| Timed wait | Call the original WaitFor helper with one second and require at least 0.8 seconds of measured elapsed time before successful completion |

The child uses the original context launch path and a separate executor process.
The list-valued shared-data call uses the original named Name/Value form; the
positional list form is ambiguous with its list-of-assignments syntax.

## Child launch fix

The original child manager held its mutex across synchronous IPC. Incoming child
notifications waited for that mutex while holding the request-processor lock,
which also blocked status requests. The test reproduced status timeouts while
the child was loading.

Child identity is now published immediately after the context allocates its
instance ID and before the launch request. The manager does not hold its mutex
across IPC and does not overwrite newer child status notifications when launch
returns. This preserves the original StartProc/helper/context design while
allowing notifications and status requests to progress. The passing parent/child
test verifies the resulting argument transfer, blocking completion, shared result
and normal shutdown.

## Evidence

[NATIVE_CIF_QUALIFICATION.json](NATIVE_CIF_QUALIFICATION.json) records all source,
recipe and artifact identities. Seven unittest cases cover 18 context lifecycle
runs. The five controller scenarios, service failure/process-loss restart,
pending-reconnect cancellation, earlier component tests and 23 standalone checks
also pass in this build. The runtime is pinned GIL-enabled CPython 3.13.15 on
Linux x86_64 with ASan/UBSan; leak sanitizer is disabled.

```powershell
docker build --progress=plain -f source_port/context-build.Dockerfile --output type=local,dest=.qualification/v0.2/cif-recheck .
../openbexi_ide/.venv/Scripts/python.exe source_port/record_native.py --evidence .qualification/v0.2/cif-recheck --cif
```

This is a v0.2 milestone. Service reconnect/checkpoint semantics and the remaining
native ownership/error-path review still require acceptance work. Broader child
failure modes and full helper/driver conformance belong to the full requirement
inventory; these three cases do not establish every CIF contract.
