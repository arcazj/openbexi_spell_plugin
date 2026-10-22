# Process and endpoint map

All as-is rows below are `VERIFIED-v0.7`; target rows are `TARGET-v0.8`.

| As-is component | Source / evidence | Boundary |
|---|---|---|
| Browser/Qt workspace → local service | IDE `procedure_service.py:Adapter`, `ProcedureService.start`, `Handler.route`; `procedure_web/app.js` | Authenticated REST/JSON, polling snapshots; host/origin validation |
| Durable service | IDE `session_http.py:SessionServer`, `session.py:Session` | Loopback HTTP or configured mTLS; session-wide controller; OS-locked SQLite authority |
| Host DAP adapter | Plugin `host_plugin/.../dap.py`, `container.py`, `local.py` | Content-Length JSON over private stdin/stdout; Docker image digest bound |
| Native adapter → IPC peer | `host_runtime/python/native.py:Bridge`, `NativeSession.start` | Private bridge subprocess; native Listener port 9980 in an isolated container |
| Native Listener → Context → Executor | Fresh `evidence/native-trace.json`; `source_port/qualify_context.py` | Separate OS PIDs; private native TCP endpoints, dynamic Context/Executor ports |
| Original Driver RPC | `driver_plugin/.../server.py:Server` | gRPC protobuf, `127.0.0.1:0`, 4 admitted RPCs, 64 KiB messages |
| Shared driver relay | `shared_plugin/.../__init__.py:Worker.handle_request`; IDE `shared_backends.py:dispatch_request` | Original RPC payload over private DAP; service attaches fence/epoch and rechecks writes |
| External DSS | `src/dss/local.py`, `driver_plugin/.../transport.py:Transport` | Independent configured HTTP and binary TCP endpoints; no universal executor port |
| Teaching DSS | `host_runtime/python/demo_dss.py:DemoDss` | Threads in adapter process; separate sockets but not a separate process |
| Desktop web display | IDE `compose.v07.yaml` | noVNC at loopback 6080; this is not the proposed v0.8 HTTPS/WSS Listener |

The trace's Docker-host PIDs included Listener 76654, Context 76696 and Executor
76787 in container `60389e51eca6`. They are observations from this one run,
not reusable runtime identities. Socket tables in the trace show private
listeners; port 9980 is `26FC` and 9981 is `26FD` in hexadecimal.

## Proposed deployment

Only reverse proxy publishes HTTPS; dev host mapping is loopback and explicitly
configured. Listener is a separate process/container. Context A and B each have
one authoritative process, their own SQLite volume, blackboard and adapter
configuration. No separate Management Service or execution-manager service.

Compose uses a fixed, bounded pool of worker containers (initial total 10),
each supervising a single active Executor subprocess and its native helpers.
Workers expose only authenticated private RPC to their bound Context; no Docker
socket is mounted. They have no authority volume and no direct DSS route.
Kubernetes uses one labeled Executor Job/Pod per active execution, launched by
the owning Context with namespace-scoped RBAC. Both are proposals requiring
qualification; there are no v0.8 deployment manifests yet.

The independent DSS container/process is reachable only through Context-owned
adapters. Context/worker RPC addresses come from explicit configuration and
service DNS. They never reuse DSS HTTP/TC addresses as executor endpoints.
