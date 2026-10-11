# Original warm-start storage on CPython 3.13

The original SPELLwsStorage class now links and runs against the ported UTIL/SYN
libraries. Its public C++ interface is retained. This qualifies the storage layer;
the full WS frame handlers and executor recovery remain open v0.2 work.

The legacy reader trusted a file-supplied size when reading into a 4,512-byte stack
buffer. It also indexed unchecked header fields and retained extra references to
decoded Python objects. The port uses a checked allocation capped at 16 MiB per
record, rejects malformed/truncated data and balances references on success and
exception paths. Long conversion failures use the original Python error bridge.

Files begin with an explicit format revision, exact CPython version and marshal
version. Each record has a sequential index, type name, byte length and CRC32,
followed by its binary payload and delimiter. Readers validate the header before
unmarshalling. Incompatible legacy/interpreter files fail explicitly; there is no
automatic migration of old interpreter frames. A failed read/reset closes the
stream, so a subsequent call cannot bypass a rejected version header.

Marshal version 4 preserves recursive containers and aliases within one record.
Aliases across separate records require the higher-level WS object graph and are
not established by this layer. The CRC detects accidental corruption; it is not
authentication. These are application-owned checkpoints, not an untrusted file
import format. Writing a record flushes the stream; crash-atomic publication and
complete-checkpoint/source identity belong to the still-open recovery integration.
Diagnostic sidecars contain record metadata without copying procedure values.

Seventeen checks pass under AddressSanitizer and UndefinedBehaviorSanitizer,
including a 1 MiB record, all truncated prefixes of a fixture, malformed lengths,
checksums/types, legacy/version mismatches, failed-reset rejection, mode/reset
behavior, cyclic aliases, 1,000 decoded code-object reference lifetimes and a
fresh Python process loading and executing code saved through the original
storage class. LeakSanitizer is disabled. See the
[evidence manifest](NATIVE_STORAGE_QUALIFICATION.json).

```powershell
docker build --progress=plain -f source_port/native-build.Dockerfile --output type=local,dest=.qualification/v0.2/native-storage-final .
python source_port/record_native.py --evidence .qualification/v0.2/native-storage-final --storage
```

The recorder also requires all 16 UTIL tests, 26 analyzer tests and three embedded
interpreter cycles to pass. Docker's export exit code alone is not qualification.
