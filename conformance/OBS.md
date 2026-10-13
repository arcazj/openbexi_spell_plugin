# Native telemetry checkpoint

This is a bounded development checkpoint, not full v0.5 or v0.6 acceptance.
`run_obs.py` starts the original native listener/context/executor and installed
original SPELL helpers, verifiers, telemetry items and result objects. The
procedure imports an assertion module; no language function, registry entry,
verifier thread or driver response is replaced. Control-flow primitives and
WaitFor interruption are outside this evidence.

The controller owns a real loopback DSS HTTP/binary TCP fixture and the original
protobuf gRPC service. Acquisitions decode real immutable binary telemetry
packets from the retained DSS database. Explicit fixture controls advance the
paused simulator clock or temporarily stop updates; they never supply a canned
TM return value. Real native IPC answers planned action prompts. RPC bytes,
prompt fields, packet database, native log, source hashes and every assertion
remain in `.qualification/v0.5/obs/<unique-run>/`. A timeout is checked against
an unread but already available source snapshot, preventing cached-sequence
progress from masquerading as a new update.

## Checked corrections

`source_port/obs_patches.py` verifies exact installed source preimages, preserves
the original files/notices, and records patched hashes. It corrects:

- Removed `Thread.isAlive()` calls in original TM and expression verification.
- `Retries=N` now makes one initial acquisition plus at most N repetitions.
- Comparison operators and operand counts reject malformed definitions before
  acquisition; invalid delays reject before native time conversion.
- Numeric comparisons retain double precision. An exactly representable float32
  input does not imply that its comparison target has float32 precision.
  Tolerance uses inclusive bounds around the expected value. Numeric telemetry
  compared to a string literal returns False without an uncaught thread error.
- `OnFalse=NOACTION` preserves the original composite result. Explicit automatic
  actions return their action value even when it compares Boolean-equal to the
  composite result. `RECHECK` requests the next sample.

The DSS proxy accepts original library-only `Retry`, `Strict` and `STEP_ID`
controls without placing them on the acquisition RPC. Relative timeout strings
are parsed through original TIME; invalid, absolute and unbounded timeouts still
reject. The HTTP transport establishes a current source sequence before waiting
for a subsequent update. The independent original-schema driver regression
suite remains applicable to these changes.

## Manual decisions and scope

LRM pp41-42 establish `OnFalse` for comparison failures. The last sentence of
p43 naming `OnFailure` is an erratum; acquisition/driver failures still use
`OnFailure`. The actual original native profile presents
ABORT/RECHECK/SKIP/CANCEL by default, consistent with p41. Page 114 describes an
illustrative profile, rather than another universal default.

The profile's original default tolerance is 0.1. Exact comparison boundary
oracles explicitly set zero tolerance instead of changing that default.
Examples 55-56 contain telemetry expressions despite their command-building
captions. The missing comma in example 37 is supplied as a syntax erratum.
Examples use catalog-backed fixed values and bounded short waits; their
placeholder spacecraft values and long example delays are not executable
satellite definitions. Timeout remains bounded to 30 seconds by this driver
profile. This evidence does not claim an unrestricted mission driver.

The report assigns only specific demonstrated rows. Parent acquisition and
verification sections, the full Verify function, all WaitFor controls/states,
all telemetry quality/link outage cases, and untested family clauses remain
open. Generic failure action tests are not evidence for a real link outage.
Remaining Python 2 syntax conflicts likewise remain open.

## Combined image

`obs_combined.Dockerfile` combines frozen DTA/TIME native host
`sha256:90f76095d9eed8117d5dd4657a7c338e4e17521278c6f3e0516bbe746e46e55a`
with driver-enabled DSS parent
`sha256:fd350eeaec46d7408384c04d0888e89776a7544c59f88c026e4c70efa1562117`,
then applies the OBS corrections. The DSS-enabled host adapter is retained.
The complete DTA native source/build manifest is retained at
`/opt/dta-native-patch`; OBS original/patched files, manifest and recipe are at
`/opt/obs-conformance-patch`. The runner checks installed files against both
manifests and compares installed OBS recipes/proxy files to the tested inputs.

```powershell
docker build --network none -f conformance/obs_combined.Dockerfile -t openbexi-spell-dss:v05-dta-time-obs-development .
python conformance/run_obs.py --image openbexi-spell-dss:v05-dta-time-obs-development
python -m pytest tests/test_original_driver.py -q
```

Earlier failing baselines and all intermediate images are retained. Final
reports use LF bytes for stable cross-platform hash binding.
