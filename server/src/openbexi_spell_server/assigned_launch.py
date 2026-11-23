"""Deliver one controller-issued start grant privately to its preconfigured worker."""

from dataclasses import asdict, dataclass
import threading

from .authority import StartGrant
from .contracts import Fault, digest, exact
from .preflight import canonical_uuid


@dataclass
class Preparation:
    execution_id: str
    request_id: str
    owner_proof_hash: str
    worker_binding_hash: str
    expires: float
    grant: StartGrant | None = None


class AssignedLaunch:
    """At most one volatile delivery per configured single-use worker slot.

    Preparing an immutable source transfers no execution authority. Only the
    original controller request may admit a start after worker verification.
    Context persists the grant hash before delivery. Lost deliveries retain the
    reservation, and a restarted Context cannot reconstruct any plaintext grant.
    """

    SCHEMA = "openbexi.worker-assignment/1"

    def __init__(self, preflight):
        self.preflight = preflight
        self.authority = preflight.authority
        self.store = self.authority.store
        self.slots: dict[str, Preparation] = {}
        self.lock = threading.Lock()
        with self.store.transaction():
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS assigned_native_results("
                "execution_id TEXT PRIMARY KEY, member_hash TEXT NOT NULL, native_status TEXT NOT NULL)"
            )
        self.authority.assigned_launch = self

    def require_active_target(self, execution_id, target):
        if (
            not target
            and self.store.db.execute(
                "SELECT 1 FROM assigned_native_results WHERE execution_id=?", (execution_id,)
            ).fetchone()
        ):
            raise Fault(403, "native_root_already_terminal")

    def record_result(self, grant, instance, status):
        if (
            not isinstance(instance, str)
            or len(instance) > 256
            or status not in ("FINISHED", "ABORTED", "ERROR")
        ):
            raise Fault(400, "invalid_native_root_observation")
        with self.authority._execution_lock(grant.execution_id), self.store.transaction():
            row = self.authority._original_grant(grant)
            member = self.store.db.execute(
                "SELECT binding_hash FROM native_members WHERE execution_id=? AND target_id='' "
                "AND instance_id=? AND origin_hash=? AND state='REGISTERED_UNPROVEN'",
                (grant.execution_id, instance, self.authority.family_origin(grant)),
            ).fetchone()
            if row["lifecycle"] != "STARTING" or member is None:
                raise Fault(403, "native_root_result_fenced")
            previous = self.store.db.execute(
                "SELECT member_hash,native_status FROM assigned_native_results WHERE execution_id=?",
                (grant.execution_id,),
            ).fetchone()
            if previous is None:
                self.store.db.execute(
                    "INSERT INTO assigned_native_results VALUES(?,?,?)",
                    (grant.execution_id, member[0], status),
                )
                self.store._event(
                    "NATIVE_ROOT_RESULT_OBSERVED",
                    {"execution_id": grant.execution_id, "native_status": status},
                )
            elif tuple(previous) != (member[0], status):
                raise Fault(409, "native_root_result_conflict")
        return {"execution_id": grant.execution_id, "native_status": status}

    def controller(self, subject, method, key, payload):
        canonical_uuid(key)
        self.authority._require(subject, "execution:start", "execution:control")
        with self.lock:
            with self.store.transaction(write=method == "execution.prepare"):
                row = self.authority._owner(subject, payload)
                slot = row["worker_slot"]
                if row["lifecycle"] != "RESERVED" or row["start_hash"]:
                    raise Fault(409, "worker_start_already_admitted")
                peer = next((p for p in self.preflight.peers.values() if p.slot == slot), None)
                if peer is None:
                    raise Fault(409, "worker_assignment_unavailable")
                pending = self.slots.get(slot)
                now = self.authority.clock()
                owner_hash = digest(payload)
                if method == "execution.prepare":
                    if pending and pending.expires > now and pending.owner_proof_hash == owner_hash:
                        if pending.request_id != key:
                            raise Fault(409, "another_launch_is_preparing")
                        return {"preparation_id": key}
                    binding, _ = self.preflight._binding(peer, row["id"])
                    pending = Preparation(row["id"], key, owner_hash, digest(binding), now + 30)
                    self.store._event(
                        "WORKER_LAUNCH_PREPARATION_REQUESTED",
                        {"execution_id": row["id"], "request_id": key, "subject": subject},
                    )
                elif (
                    pending is None
                    or pending.request_id != key
                    or pending.owner_proof_hash != owner_hash
                    or pending.expires <= now
                ):
                    raise Fault(409, "worker_launch_preparation_expired")
                elif method == "execution.launch_status":
                    try:
                        self.preflight.require_ready(row)
                    except Fault as error:
                        if error.code != "worker_preflight_required":
                            raise
                        return {"preparation_id": key, "ready": False}
                    return {"preparation_id": key, "ready": True}
            if method == "execution.prepare":
                self.slots[slot] = pending
                return {"preparation_id": key}
            if method != "execution.launch":
                raise Fault(404, "method_not_available")
            # Admission takes the normal execution mutex, revalidates the
            # original owner, source preflight and incarnation, and commits the
            # grant hash. No worker API calls admit_start.
            grant = self.authority.admit_start(subject, payload)
            pending.grant = grant
            return {
                "execution_id": grant.execution_id,
                "request_id": grant.request_id,
                "state": "ADMITTED",
            }

    def worker(self, peer, path, body):
        if self.preflight.peers.get(peer.fingerprint) != peer:
            raise Fault(403, "worker_identity_required")
        poll = path == "/v1/worker/assignment"
        fields = {"schema", "context_id"}
        if not poll:
            if path != "/v1/worker/start-delivery":
                raise Fault(404, "route_not_available")
            fields |= {"execution_id", "preparation_id"}
        exact(body, fields)
        if body["schema"] != self.SCHEMA or body["context_id"] != self.store.context_id:
            raise Fault(403, "worker_scope_denied")
        if not poll:
            canonical_uuid(body["execution_id"])
            canonical_uuid(body["preparation_id"])
        with self.lock:
            pending = self.slots.get(peer.slot)
            if pending is None or pending.expires <= self.authority.clock():
                if poll:
                    return {"assignment": None}
                raise Fault(409, "worker_delivery_unavailable")
            if not poll and (
                pending.execution_id != body["execution_id"]
                or pending.request_id != body["preparation_id"]
            ):
                raise Fault(403, "worker_delivery_fenced")
            with self.store.transaction(write=not poll and pending.grant is not None):
                binding, expected = self.preflight._binding(peer, pending.execution_id)
                if digest(binding) != pending.worker_binding_hash:
                    if poll:
                        return {"assignment": None}
                    raise Fault(403, "worker_delivery_fenced")
                if poll:
                    return {
                        "assignment": {
                            "execution_id": pending.execution_id,
                            "preparation_id": pending.request_id,
                            "source_sha256": expected["source_sha256"],
                            "runtime_image": expected["runtime_image"],
                        }
                    }
                grant = pending.grant
                if grant is None:
                    return {"grant": None}
                row = self.authority._grant(grant)
                self.preflight.require_ready(row)
                self.store._event(
                    "WORKER_START_DELIVERY_ATTEMPTED",
                    {"execution_id": grant.execution_id, "request_id": grant.request_id},
                )
            # Pop only after a successful audit commit, before sending. A lost
            # response cannot trigger redelivery or a second consumption.
            del self.slots[peer.slot]
            return {"grant": asdict(grant)}
