# Original bytecode analyzer on CPython 3.13

SPELLbytecode now obtains instruction metadata from `dis.get_instructions` and
statement/exception regions from the original source AST. It no longer walks raw
opcode bytes until an obsolete STOP_CODE, assumes old CALL/SETUP_EXCEPT opcodes,
or copies an outdated opcode-name table. The original analyzer interface remains.

The compiler records source text for its code object and nested code objects in
an interpreter-local compatibility module. Entries use object identity and weak
references. This matters because distinct Python code objects can compare equal
despite different filenames or non-executable source text. Releasing code removes
its source entry; no native static Python reference survives interpreter shutdown.
The compatibility module adds no SPELL names to user builtins or namespaces.

For an imported code object not compiled by this helper, the analyzer reads its
file and accepts it only if recompiling produces equivalent code. This fallback
establishes code equivalence, not the historical identity of comments or spelling.
After acceptance, the source snapshot is bound to that code object's identity.
Missing or incompatible source fails explicitly. New source edits are not applied
to metadata for an existing paused frame. Persistent recovery still needs the
complete source/format identity checks described in the recovery design.

Scope analysis excludes nested function/class bodies from the enclosing model
and recognizes decorated functions. Try-body, individual handler, else and finally
regions are distinguished, including one-line bodies and exception groups. Nested
try-end queries select the innermost matching block. Multiline simple statements
remain grouped. Constant/local-return classification follows modern disassembly;
instruction extent does not depend on a byte-value sentinel. CPython's validated
line setter remains responsible for whether a requested runtime jump is legal.

Fourteen new checks pass, including nested scopes/handlers, try/finally, exception
groups, decorated functions, multiline statements, return classification, source
changes/missing source, equal-but-distinct code objects, and 500 source-registry
lifetime cycles. The combined suites pass 16 UTIL tests, 57 analyzer/watch tests,
17 storage tests, and three standalone interpreter cycles with address/undefined
behavior sanitizers. LeakSanitizer is disabled. This does not close the full
executor integration or warm-start gate.

```powershell
docker build --progress=plain -f source_port/native-build.Dockerfile --output type=local,dest=.qualification/v0.2/native-bytecode-qualified .
python source_port/record_native.py --evidence .qualification/v0.2/native-bytecode-qualified --bytecode
```

See [the qualification manifest](NATIVE_BYTECODE_QUALIFICATION.json).
API references: [disassembly](https://docs.python.org/3.13/library/dis.html) and
[source AST](https://docs.python.org/3.13/library/ast.html).
