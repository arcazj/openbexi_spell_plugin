# Executor frame access and original library inventory

The execution model, executor dispatcher and service dispatcher now read frame
code, filename, function name and current line using CPython's public APIs.
`FrameCode` balances the new reference returned by `PyFrame_GetCode`, including
temporary use in the three original analyzer base constructors. The frame keeps
the underlying code alive for the original borrowed-reference analyzer contract.
See the [CPython frame API](https://docs.python.org/3.13/c-api/frame.html).

Two additional native tests exercise nested Unicode filenames, all four real
trace events, invalid input and 2,000 reference-count/lifetime checks. The utility
suite now has 18 passing tests; analysis/watch has 57, storage has 17, and the
embedding executable passes three owned-interpreter cycles. ASan and UBSan pass;
LeakSanitizer remains disabled. Dispatcher/model units pass syntax checks but
have not yet been linked into a qualified complete executor.

The build now reads the original `*_v3_la_SOURCES` assignments in all 16 library
Makefiles. This identifies 143 Python 3 translation units, with their original
manifest hashes recorded in [qualification evidence](NATIVE_FRAMES_QUALIFICATION.json).
135 pass compilation/syntax checks; eight remain blocked by frame manager or
warm-start compatibility. All 73 units in the remaining libraries pass, including
the two terminal client units after installing their ncurses development headers.
This is a syntax inventory, not a claim that all libraries link or run correctly.

Earlier 63-unit probes included two Python 2-only WS handlers. The original
Python 3 build excludes both `SPELLwsClassDataHandler.C` and
`SPELLwsInstanceDataHandler.C`; no replacement is needed to match that build.
`SPELLexecutorDefaults.C` is also absent from its library's original source list.
These files remain in the authoritative source archive. Historical reports retain
their original counts; they are not retroactively rewritten.

Reproduce into a fresh evidence directory and validate with:

```powershell
docker build --progress=plain -f source_port/native-build.Dockerfile --output type=local,dest=.qualification/v0.2/native-library-inventory .
python source_port/record_native.py --evidence .qualification/v0.2/native-library-inventory --frames
```

The complete native runtime, DTA behavior, context setup/cleanup and persistent
WS frame recovery remain v0.2 release gates. This milestone does not promote a
release or install a native test extension into the working IDE.
