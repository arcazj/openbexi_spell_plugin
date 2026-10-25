# v0.8 prelaunch multi-service Compose qualification

**This is an executable, security-isolated prelaunch staging profile, not a
native SPELL v0.8 runtime, Kubernetes release, user-facing web service or
production migration.** It leaves `runtime_enabled=false` everywhere. All
eleven mandatory full-release gates remain unqualified pending independent
evidence. Published v0.7 is untouched.

## Processes and trust edges

- Gateway: certificate-authenticated desktop API, loopback **127.0.0.1:19443**
  only. It pins Listener's TLS leaf and accepts only registered client pins.
- Listener: independent process on private control network, pins downstream
  Context A and B identities and restricts each principal's Context scopes.
- Context A/B: independent processes, distinct SQLite state directories and
  Context incarnations; they only trust the exact Listener certificate.
- Independent DSS: separate process on isolated `driver` network with Context
  services, not accessible from the gateway/Listener network and not exposed
  on the host. No native driver binding, TC execution or worker is enabled.
- No Docker socket, host PID/network mode, privileged container, extra caps,
  executable writable root filesystem or cross-Context authority volume.

The control and driver networks are internal. A separate gateway-only ingress
bridge handles Docker loopback publication; no Listener, Context or DSS
container belongs to it. The gateway is the only published loopback port. Each process mounts **only its own role's certificate/key**
from a read-only private directory. The disposable CA and client keys are
not embedded in images or stored in the repository.

## Reproduce the bounded prelaunch exercise (Linux, Docker Compose v2)

Create a new private directory *outside* the Git checkout. An existing
directory is rejected to prevent trust-key and authority reuse:

```bash
export V08_DEPLOY_ROOT="$(mktemp -d -p /tmp v08-new.XXXXXXXX)"
rmdir "$V08_DEPLOY_ROOT"  # provisioning requires nonexistence
export V08_SERVICE_UID="$(id -u)"  # must be unprivileged and own state dirs
export V08_GATEWAY_PORT=19443
python3.13 deploy/v0.8/provision.py --output "$V08_DEPLOY_ROOT"
docker compose -f deploy/v0.8/compose.yaml config --quiet
docker compose -f deploy/v0.8/compose.yaml up -d --build --wait
python3.13 deploy/v0.8/qualify_compose.py --root "$V08_DEPLOY_ROOT" --phase before --output /tmp/v08-before.json
docker compose -f deploy/v0.8/compose.yaml restart context-a
python3.13 deploy/v0.8/qualify_compose.py --root "$V08_DEPLOY_ROOT" --phase after --previous /tmp/v08-before.json --output /tmp/v08-after.json
docker compose -f deploy/v0.8/compose.yaml down --volumes
```

**Never upload `$V08_DEPLOY_ROOT`**: it contains CA, per-service and per-user
private keys, and state data. Use operator-managed production PKI, rotation,
recovery policies, image signature verification and volume backups before
considering any real deployment. The tool intentionally uses a one-day
qualification-only CA and no credential rotation.

## What the hosted integration actually proves

The new GitHub Actions job boots and exercises all five real containers,
verifies pinned TLS through Gateway → Listener → each Context, three different
client certificates, Context-scope denial, read-only observer privileges,
unauthorized public execution denial, separate blackboards, durable
idempotency, and restart of Context A without altering Context B. The
independent DSS healthcheck is run inside its container. Evidence is
redacted and source-bound to the exact Actions run.

**What it does not prove:** native Executor/children/PIDs in this Compose
topology, runtime Run/Debug, safe owner handoff, actual driver effects,
failure partitions, recovery to a new worker, dynamic rollouts, browser WSS,
full-scale load, production ingress, Kubernetes workload admission or stable
distribution. Do not upgrade `compose.qualified` or publish v0.8 based on
this prelaunch smoke test.
