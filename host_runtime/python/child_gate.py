"""One-shot admission before native Context creates a root or child Executor.

The Unix endpoint is confined to one worker. SO_PEERCRED, immutable executable
and the agent's owned Listener parent authenticate the native Context process.
Its exact PID bindings authenticate only the original admitted Executor members.
Context service RPC still uses the original certificate/grant/winner proof.
This provider supplies no family pause, recovery, release or resume proof.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import select
import socket
import struct
import threading
import time
import uuid

from openbexi_spell_server.contracts import canonical, decode, exact
from openbexi_spell_server.family import child_grant, FamilyAdmission
from openbexi_spell_server.snapshots import source_path


class NativeChildGate:
    def __init__(
        self, request, route, entrypoint, root_instance, root_arguments, root_check
    ):
        self.request = request
        self.route = route
        self.entrypoint = entrypoint
        self.root_instance = root_instance
        self.root_arguments = root_arguments
        self.root_check = root_check
        self.attempted = set()
        self.started = {}
        self.lock = threading.Lock()

    def admit(self, body):
        exact(
            body,
            {
                "schema",
                "instance_id",
                "parent_instance_id",
                "entrypoint",
                "arguments",
                "mode",
            },
        )
        if body["schema"] != "openbexi.native-start/1":
            raise ValueError("Native start schema differs")
        source_path(body["entrypoint"])
        if not body["entrypoint"].endswith(".py"):
            raise ValueError("Native entrypoint differs")
        procedure = body["entrypoint"][:-3]
        instance = body["instance_id"]
        if (
            type(instance) is not str
            or not instance.startswith(procedure + "#")
            or not instance[len(procedure) + 1 :].isascii()
            or not instance[len(procedure) + 1 :].isdecimal()
            or not 1 <= len(instance[len(procedure) + 1 :]) <= 9
            or str(int(instance[len(procedure) + 1 :]))
            != instance[len(procedure) + 1 :]
            or type(body["arguments"]) is not str
            or len(body["arguments"].encode()) > 16384
            or type(body["parent_instance_id"]) is not str
        ):
            raise ValueError("Native start identity differs")
        exact(body["mode"], {"automatic", "visible", "blocking"})
        if any(type(value) is not bool for value in body["mode"].values()):
            raise ValueError("Native start mode differs")
        with self.lock:
            if instance in self.attempted or len(self.attempted) >= 65:
                raise ValueError("Native start already attempted or capacity reached")
            # Retain the attempt BEFORE any RPC. Unknown outcomes never retry,
            # restamp provenance, reconstruct a token or repeat physical start.
            self.attempted.add(instance)
            if not body["parent_instance_id"]:
                if (
                    instance != self.root_instance
                    or body["entrypoint"] != self.entrypoint
                    or body["arguments"] != self.root_arguments
                    or body["mode"]
                    != dict(automatic=True, visible=True, blocking=False)
                    or self.started
                ):
                    raise ValueError("Only the original root may start")
                self.root_check()
                self.started[instance] = None
                return
            parent = body["parent_instance_id"]
            if parent not in self.started:
                raise ValueError("Native parent was not admitted")
            payload = dict(
                request_id=str(uuid.uuid4()),
                parent_admission_id=self.started[parent],
                entrypoint=body["entrypoint"],
                arguments_sha256=hashlib.sha256(body["arguments"].encode()).hexdigest(),
                mode=body["mode"],
            )
            reply = self.route.call(
                {**self.request, **payload},
                path="/v1/worker/child-admit",
                schema="openbexi.worker/2",
            )
            exact(
                reply,
                {
                    "admitted",
                    "child_grant",
                    "hold_retained",
                    "native_start_qualified",
                    "runtime_enabled",
                },
            )
            grant = child_grant(reply["child_grant"])
            from openbexi_spell_server.launch import start_grant
            from openbexi_spell_server.contracts import digest

            original = start_grant(self.request["grant"])
            if (
                reply["admitted"] is not True
                or reply["hold_retained"] is not True
                or reply["native_start_qualified"] is not False
                or reply["runtime_enabled"] is not False
                or grant.execution_id != original.execution_id
                or grant.authority_incarnation != original.authority_incarnation
                or grant.parent_admission_id != self.started[parent]
                or grant.entrypoint != body["entrypoint"]
                or grant.origin_hash != FamilyAdmission.origin(original)
                or grant.operation_digest != digest(payload)
            ):
                raise ValueError("Native child admission receipt differs")
            receipt = self.route.call(
                {**self.request, "child_grant": asdict(grant)},
                path="/v1/worker/child-consume",
                schema="openbexi.worker/2",
            )
            if canonical(receipt) != canonical(
                dict(
                    consumed=True,
                    admission_id=grant.admission_id,
                    execution_id=original.execution_id,
                    hold_retained=True,
                    native_start_qualified=False,
                    runtime_enabled=False,
                )
            ):
                raise ValueError("Native child consumption receipt differs")
            self.started[instance] = grant.admission_id


class NativeAdmissionServer:
    def __init__(
        self,
        path,
        executable,
        listener,
        gate,
        *,
        controls=None,
        executor=None,
        report=lambda *_args, **_kwargs: None,
    ):
        self.path = str(path)
        self.executable = Path(executable).resolve(strict=True)
        if not os.statvfs(self.executable).f_flag & os.ST_RDONLY:
            raise ValueError("Native Context must be immutable")
        self.listener = listener
        self.gate = gate
        self.report = report
        self.controls = controls
        self.executor = (
            None if executor is None else Path(executor).resolve(strict=True)
        )
        if (
            self.executor is not None
            and not os.statvfs(self.executor).f_flag & os.ST_RDONLY
        ):
            raise ValueError("Native Executor must be immutable")
        self.members = {}
        self.member_pids = {}
        self.executor_sha256 = (
            None
            if self.executor is None
            else hashlib.sha256(self.executor.read_bytes()).hexdigest()
        )
        self.control_denials = threading.Event()
        self.consume_denials = threading.Event()
        self.disabled_mutations = set()
        self.context_pid = None
        self.pidfd = None
        self.stop = threading.Event()
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.path)
        self.socket.listen(4)
        self.socket.settimeout(0.1)
        self.thread = threading.Thread(
            target=self.serve, name="native-before-spawn", daemon=True
        )
        self.thread.start()

    def authenticate(self, stream):
        pid, uid, _gid = struct.unpack(
            "3i", stream.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        )
        process = self.listener()
        if process is None or process.poll() is not None or uid != os.getuid():
            raise ValueError("Native Listener unavailable")
        instance = self.member_pids.get(pid)
        if instance is not None:
            handle = self.members[instance][1]
            if (
                select.select([handle], [], [], 0)[0]
                or self.pidfd is None
                or select.select([self.pidfd], [], [], 0)[0]
            ):
                raise ValueError("Native Executor/Context incarnation differs")
            self.process_identity(pid, self.context_pid, self.executor)
            if select.select([handle, self.pidfd], [], [], 0)[0]:
                raise ValueError("Native Executor/Context incarnation differs")
            return "executor", instance
        if self.context_pid is not None:
            if pid != self.context_pid or select.select([self.pidfd], [], [], 0)[0]:
                raise ValueError("Native Context incarnation differs")
            self.process_identity(pid, process.pid, self.executable)
            if select.select([self.pidfd], [], [], 0)[0]:
                raise ValueError("Native Context incarnation differs")
            return "context", None
        # Parse after the final ')' since Linux comm names may include spaces
        # and parentheses. Bind the exact owned parent, never a name-only scan.
        self.pidfd = self.pin_process(pid, process.pid, self.executable)
        self.context_pid = pid
        return "context", None

    @staticmethod
    def process_identity(pid, parent, executable):
        status = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if (
            int(status[1]) != parent
            or Path(f"/proc/{pid}/exe").resolve(strict=True) != executable
        ):
            raise ValueError("Native process parent/executable differs")
        return status[19]  # Linux starttime, bound on both sides of pidfd_open.

    @classmethod
    def pin_process(cls, pid, parent, executable):
        before = cls.process_identity(pid, parent, executable)
        handle = os.pidfd_open(pid, 0)
        try:
            if (
                before != cls.process_identity(pid, parent, executable)
                or select.select([handle], [], [], 0)[0]
            ):
                raise ValueError("Native process incarnation changed")
        except BaseException:
            os.close(handle)
            raise
        return handle

    def register(self, body):
        exact(body, {"schema", "instance_id", "pid"})
        if (
            body["schema"] != "openbexi.native-member/1"
            or type(body["instance_id"]) is not str
            or body["instance_id"] not in self.gate.started
            or type(body["pid"]) is not int
            or not 1 <= body["pid"] <= 2**31 - 1
            or self.executor is None
        ):
            raise ValueError("Native member identity was not admitted")
        instance, pid = body["instance_id"], body["pid"]
        if (
            instance in self.members
            or pid in self.member_pids
            or len(self.members) >= 65
        ):
            raise ValueError("Native member already bound or capacity reached")
        handle = self.pin_process(pid, self.context_pid, self.executor)
        try:
            if self.controls is None:
                raise ValueError("Native member registration provider unavailable")
            self.controls.bind_member(
                instance,
                pid,
                self.context_pid,
                int(self.process_identity(pid, self.context_pid, self.executor)),
                self.executor_sha256,
            )
            if select.select([handle, self.pidfd], [], [], 0)[0]:
                raise ValueError("Native member exited during registration")
        except BaseException:
            os.close(handle)
            raise
        self.members[instance] = (pid, handle)
        self.member_pids[pid] = instance

    def dispatch(self, role, instance, body):
        if role != "executor" and body.get("schema") == "openbexi.native-denied/1":
            raise ValueError("Native denied diagnostic role differs")
        if role == "executor":
            if body.get("schema") == "openbexi.native-denied/1":
                exact(body, {"schema", "instance_id", "operation"})
                operation = body["operation"]
                if (
                    body["instance_id"] != instance
                    or type(operation) is not str
                    or not 1 <= len(operation) <= 64
                    or any(
                        ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
                        for ch in operation
                    )
                ):
                    raise ValueError("Native denied diagnostic scope differs")
                key = (instance, operation)
                if key not in self.disabled_mutations:
                    if len(self.disabled_mutations) >= 128:
                        raise ValueError("Native denied diagnostic capacity reached")
                    self.disabled_mutations.add(key)
                    self.report("native-mutation-denied", operation=operation)
                # It is never an admission, including after duplicate reports.
                raise ValueError("Unqualified native mutation rejected")
            if (
                body.get("schema") != "openbexi.native-consume/1"
                or body.get("instance_id") != instance
                or self.controls is None
            ):
                raise ValueError("Native member scope denied")
            try:
                self.controls.consume(body)
            except Exception:
                self.consume_denials.set()
                self.report("native-before-consume-denied")
                raise
            self.report("native-before-consume-admitted")
            return
        if role != "context":
            raise ValueError("Native role denied")
        if body.get("schema") == "openbexi.native-member/1":
            self.register(body)
            self.report("native-executor-bound")
            return
        if body.get("schema") == "openbexi.native-control/1":
            try:
                if self.controls is None:
                    raise ValueError("Native control provider unavailable")
                self.controls.forward(body)
            except Exception:
                self.control_denials.set()
                self.report("native-before-forward-denied")
                raise
            self.report("native-before-forward-admitted")
            return
        self.report(
            "native-before-spawn-request",
            child=bool(body.get("parent_instance_id")),
        )
        self.gate.admit(body)
        self.report(
            "native-before-spawn-admitted",
            child=bool(body.get("parent_instance_id")),
        )

    def serve(self):
        while not self.stop.is_set():
            try:
                stream, _ = self.socket.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with stream:
                try:
                    stream.settimeout(0.5)
                    role, instance = self.authenticate(stream)
                    raw = bytearray()
                    deadline = time.monotonic() + 1.0
                    while b"\n" not in raw:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError(
                                "Native admission frame deadline expired"
                            )
                        stream.settimeout(min(0.5, remaining))
                        part = stream.recv(32769 - len(raw))
                        if not part or len(raw) + len(part) > 32768:
                            raise ValueError("Native start request exceeds bound")
                        raw.extend(part)
                    body = decode(bytes(raw))
                    self.dispatch(role, instance, body)
                    stream.sendall(b"ALLOW\n")
                except Exception as error:
                    self.report(
                        "native-before-spawn-denied",
                        error_type=type(error).__name__,
                        reason=str(error)[:128]
                        if isinstance(error, ValueError)
                        else "admission_unavailable",
                    )
                    # Never acknowledge after response loss, partial failure or
                    # an uncertain admission. No raw arguments or authority logs.
                    try:
                        stream.sendall(b"DENY\n")
                    except OSError:
                        pass

    def close(self):
        self.stop.set()
        self.socket.close()
        self.thread.join(timeout=12)
        if self.thread.is_alive():
            raise RuntimeError("Native admission callback did not settle")
        if self.pidfd is not None:
            os.close(self.pidfd)
        for _pid, handle in self.members.values():
            os.close(handle)
