"""Pinned single-host worker identity and source preflight. Never a launch grant."""

from dataclasses import dataclass
import json
import uuid

from .contracts import Fault, canonical, decode, digest, exact, fingerprint, identifier


@dataclass(frozen=True)
class WorkerPeer:
    fingerprint: str
    slot: str
    incarnation: str


def canonical_uuid(value):
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError("noncanonical")
    except (ValueError, TypeError, AttributeError) as error:
        raise Fault(400, "invalid_worker_id") from error
    return value


class WorkerPreflight:
    def __init__(self, authority, catalog, config, listener_pin):
        exact(config, {"profile", "identities"})
        if config["profile"] != "single-host-preflight":
            raise ValueError(
                "Only single-host preflight is qualified; Kubernetes identity is unsupported"
            )
        identities = config["identities"]
        if type(identities) is not dict or not 1 <= len(identities) <= 10:
            raise ValueError("Invalid worker identities")
        self.authority, self.store, self.catalog = authority, authority.store, catalog
        self.peers, bindings = {}, set()
        for pin, value in identities.items():
            fingerprint(pin)
            exact(value, {"slot", "incarnation"})
            slot, incarnation = identifier(value["slot"]), identifier(value["incarnation"])
            if (
                pin == listener_pin
                or authority.worker_slots.get(slot) != incarnation
                or slot in bindings
            ):
                raise ValueError("Worker identity/slot binding is ambiguous")
            bindings.add(slot)
            self.peers[pin] = WorkerPeer(pin, slot, incarnation)
        with self.store.transaction():
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS worker_preflights("
                "id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,peer TEXT NOT NULL,"
                "request_id TEXT NOT NULL,binding TEXT NOT NULL,expires REAL NOT NULL,state TEXT NOT NULL,"
                "UNIQUE(peer,request_id))"
            )
            self.store.db.execute(
                "UPDATE worker_preflights SET state='INVALIDATED' WHERE state IN ('PENDING','VERIFIED')"
            )
            if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 3:
                self.store.db.execute("PRAGMA user_version=3")

    def _binding(self, peer, execution_id):
        row = self.authority._execution(execution_id)
        self.authority._require(row["owner"], "execution:control")
        self.authority._session(row["owner"], row["connection_id"])
        if (
            row["authority_incarnation"] != self.store.incarnation
            or row["lifecycle"] != "RESERVED"
            or row["control_state"] != "OWNED"
            or not row["cap_hash"]
            or row["worker_slot"] != peer.slot
            or row["worker_incarnation"] != peer.incarnation
        ):
            raise Fault(403, "worker_preflight_fenced")
        inventory = json.loads(row["inventory"])
        expected = self.catalog.entries.get(row["procedure_id"])
        if expected is None or any(
            inventory.get(k) != expected[k]
            for k in ("source_revision", "source_sha256", "runtime_image", "driver_binding")
        ):
            raise Fault(403, "source_binding_not_approved")
        return dict(
            authority_incarnation=self.store.incarnation,
            execution_id=execution_id,
            procedure_id=row["procedure_id"],
            worker_slot=peer.slot,
            worker_incarnation=peer.incarnation,
            worker_generation=row["worker_generation"],
            control_epoch=row["epoch"],
            connection_id=row["connection_id"],
            connection_generation=row["connection_generation"],
            inventory_sha256=digest(inventory),
        ), expected

    def handle(self, peer, path, body):
        if self.peers.get(peer.fingerprint) != peer:
            raise Fault(403, "worker_identity_required")
        fields = {"schema", "context_id", "execution_id"}
        if path == "/v1/worker/challenge":
            exact(body, fields | {"request_id"})
            canonical_uuid(body["request_id"])
        elif path == "/v1/worker/verify":
            exact(body, fields | {"challenge_id", "source_sha256"})
            canonical_uuid(body["challenge_id"])
            fingerprint(body["source_sha256"])
        else:
            raise Fault(404, "route_not_available")
        if body["schema"] != "openbexi.worker/1" or body["context_id"] != self.store.context_id:
            raise Fault(403, "worker_scope_denied")
        execution_id = canonical_uuid(body["execution_id"])
        with self.authority._execution_lock(execution_id):
            with self.store.transaction():
                binding, expected = self._binding(peer, execution_id)
                encoded = canonical(binding).decode()
                if path.endswith("challenge"):
                    old = self.store.db.execute(
                        "SELECT * FROM worker_preflights WHERE peer=? AND request_id=?",
                        (peer.fingerprint, body["request_id"]),
                    ).fetchone()
                    if old:
                        if (
                            old["execution_id"] != execution_id
                            or old["binding"] != encoded
                            or old["expires"] <= self.authority.clock()
                            or old["state"] not in ("PENDING", "VERIFIED")
                        ):
                            raise Fault(409, "worker_challenge_conflict")
                        challenge_id, expires = old["id"], old["expires"]
                    else:
                        if (
                            self.store.db.execute(
                                "SELECT COUNT(*) FROM worker_preflights"
                            ).fetchone()[0]
                            >= 128
                        ):
                            raise Fault(503, "worker_preflight_capacity_reached")
                        if (
                            self.store.db.execute(
                                "SELECT COUNT(*) FROM worker_preflights WHERE peer=?",
                                (peer.fingerprint,),
                            ).fetchone()[0]
                            >= 8
                        ):
                            raise Fault(503, "worker_identity_preflight_capacity_reached")
                        challenge_id, expires = str(uuid.uuid4()), self.authority.clock() + 30
                        self.store.db.execute(
                            "INSERT INTO worker_preflights VALUES(?,?,?,?,?,?,?)",
                            (
                                challenge_id,
                                execution_id,
                                peer.fingerprint,
                                body["request_id"],
                                encoded,
                                expires,
                                "PENDING",
                            ),
                        )
                        self.store._event(
                            "WORKER_PREFLIGHT_CHALLENGED",
                            {"execution_id": execution_id, "challenge_id": challenge_id},
                        )
                    return dict(
                        challenge_id=challenge_id,
                        expires_at=expires,
                        binding=binding,
                        manifest=decode(expected["manifest"]),
                        source_sha256=expected["source_sha256"],
                        runtime_enabled=False,
                    )
                challenge = self.store.db.execute(
                    "SELECT * FROM worker_preflights WHERE id=?", (body["challenge_id"],)
                ).fetchone()
                if (
                    challenge is None
                    or challenge["execution_id"] != execution_id
                    or challenge["peer"] != peer.fingerprint
                    or challenge["binding"] != encoded
                    or challenge["expires"] <= self.authority.clock()
                    or challenge["state"] not in ("PENDING", "VERIFIED")
                    or body["source_sha256"] != expected["source_sha256"]
                ):
                    raise Fault(403, "worker_preflight_fenced")
                if challenge["state"] != "VERIFIED":
                    self.store.db.execute(
                        "UPDATE worker_preflights SET state='VERIFIED' WHERE id=?",
                        (challenge["id"],),
                    )
                    self.store._event(
                        "WORKER_SOURCE_PREFLIGHT_VERIFIED",
                        {
                            "execution_id": execution_id,
                            "challenge_id": challenge["id"],
                            "source_sha256": expected["source_sha256"],
                        },
                    )
                return dict(
                    verified=True,
                    execution_id=execution_id,
                    source_sha256=expected["source_sha256"],
                    runtime_enabled=False,
                )

    def require_ready(self, row):
        peer = next((p for p in self.peers.values() if p.slot == row["worker_slot"]), None)
        if peer is None:
            raise Fault(403, "worker_preflight_required")
        binding, _ = self._binding(peer, row["id"])
        found = self.store.db.execute(
            "SELECT 1 FROM worker_preflights WHERE execution_id=? AND peer=? AND binding=? AND state='VERIFIED' AND expires>?",
            (row["id"], peer.fingerprint, canonical(binding).decode(), self.authority.clock()),
        ).fetchone()
        if not found:
            raise Fault(403, "worker_preflight_required")
