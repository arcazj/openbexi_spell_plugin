# Original DTA native types

The five original SPELL DTA translation units now link and run with CPython
3.13.14 under ASan/UBSan. The original `Var` validation, value model, constraints,
notification decisions and prompting code remain the implementation. The port
repairs the Python bindings and ownership around those classes.

`DataContainer` and `Var` are allocated as heap types for each interpreter.
Container methods validate arguments and initialization before accessing native
state. Variable subclasses use actual Python subtype checks. Reinitialization
releases the previous native instance only after successful construction.
Containers own one dictionary reference; dictionary entries own their Vars.
Destruction detaches each Var's borrowed parent pointer and releases the dictionary.
Garbage collection sees the dictionary and can collect cycles through subclasses.

The old custom iterator used a borrowed dictionary and leaked its own allocation.
The port uses the public dictionary iterator, which retains the dictionary and
detects size changes. Dictionary insertion order replaces the redundant string
key list, preserving numeric key identity. A surviving iterator retains values
after container destruction without retaining dangling parent pointers.

`SPELLpyValue` still stores its original C++ value representation. Nested values
release temporary Python objects; assignment replaces rather than appends to old
collections. Text preserves Unicode and embedded NUL characters. Cyclic input
and nesting beyond 128 levels fail explicitly before exhausting the native stack.
Integer-to-float assignment uses the original 64-bit value without narrowing it
through a C `int`. Original type/format constants and the unformatted `Var.str()`
behavior are preserved; formatting is applied by the original CIF notification
path, which is not qualified by these component tests.

Notifications are disabled by the original global flag in the component fixture.
When enabled without an active executor, notification and prompt requests now
raise an explicit SPELL exception instead of reaching the original null-singleton
assertion. Live CIF notifications, interactive prompts and operational DSS effects
remain integration gates.

[Qualification evidence](NATIVE_DTA_QUALIFICATION.json) records 18 isolated-process
cases and 3,000 additional container lifetimes across three owned interpreter
startup/shutdown cycles. Cases cover ownership, iteration, constraints, subclass
cycles, failed initialization, numeric conversion, missing executor errors and
bounded recursion. The earlier 21 UTIL, 57 analysis/watch, 12 manager and 17
storage checks and three UTIL embedding cycles still pass. LeakSanitizer is
disabled; reference counts, weak references, GC and sanitizer checks cover the
stated cases rather than proving every original allocation leak-free.

The complete source runtime remains unreleased: WS integration and the real
executor/context/CIF lifecycle still gate v0.2. The installed v0.1 testing adapter
and source-alpha wheel are unchanged. The native test libraries are isolated
qualification artifacts.

```powershell
docker build --progress=plain -f source_port/native-build.Dockerfile --output type=local,dest=.qualification/v0.2/native-dta-03 .
python source_port/record_native.py --evidence .qualification/v0.2/native-dta-03 --dta
```

CPython API references: [heap types](https://docs.python.org/3.13/c-api/type.html),
[type slots and ownership](https://docs.python.org/3.13/c-api/typeobj.html), and
[cyclic garbage collection](https://docs.python.org/3.13/c-api/gcsupport.html).
