# Frame creation ownership

The original `SPELLpythonHelper` frame factories now return exactly the owned
reference supplied by `PyFrame_New`. They no longer add unmatched references to
the frame, code or globals. Function input is validated, errors are translated
through the original error helper, and GIL ownership is explicit. Procedure
loads update `__main__.__file__` to the current filename rather than retaining
the first procedure's filename after a reload.

Three additional native checks cover 2,000 procedure-frame lifetimes, 1,000
function-frame lifetimes with unchanged namespace identity/reference counts,
and invalid input. [Qualification evidence](NATIVE_FACTORY_QUALIFICATION.json)
records 21 utility, 57 analysis/watch and 17 storage tests, plus three embedded
interpreter cycles, passing with ASan/UBSan. LeakSanitizer remains disabled.

The warm-start interface header now forward-declares its private `SPELLwsFrame`
dependency. The implementation retains the real include. This permits the
executor interpreter, service interpreter and dictionary handler to compile
without exposing obsolete dynamic-frame internals in their headers. The original
Python 3 library inventory is now 138/143 passing compilation/syntax checks.
Remaining failures are the frame manager and four warm-start implementation units.

Frame creation is not frame resumption. The original executor's evaluation loop
and complete WS integration remain open v0.2 gates; this change does not promote
a release or make `PyEval_EvalFrame` on a constructed frame a supported recovery
mechanism. The separately qualified recovery experiments allocate live frames
through CPython evaluation before restoring their saved state.

```powershell
docker build --progress=plain -f source_port/native-build.Dockerfile --output type=local,dest=.qualification/v0.2/native-frame-factory .
python source_port/record_native.py --evidence .qualification/v0.2/native-frame-factory --factory
```
