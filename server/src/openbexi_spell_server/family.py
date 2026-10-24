"""Single-use child admission ledger; no native child start/teardown provider.

Every child occupies the same Context reservation namespace as top-level runs.
An admission is not a launch receipt or quiescence proof. Neither timeout nor
native FINISHED releases its hold. The native before-RUN hook remains a gate.
"""

from dataclasses import asdict, dataclass, fields
import hmac
import json
import secrets
import sqlite3
import uuid

from .authority import secret_hash
from .contracts import Fault, canonical, digest, exact, fingerprint
from .preflight import canonical_uuid
from .snapshots import source_path


@dataclass(frozen=True)
class ChildGrant:
    admission_id: str
    execution_id: str
    authority_incarnation: str
    parent_admission_id: str | None
    procedure_id: str
    entrypoint: str
    origin_hash: str
    operation_digest: str
    token: str


def child_grant(value):
    exact(value, {f.name for f in fields(ChildGrant)})
    for key in ("admission_id", "execution_id", "authority_incarnation"):
        canonical_uuid(value[key])
    if value["parent_admission_id"] is not None:
        canonical_uuid(value["parent_admission_id"])
    from .contracts import identifier

    identifier(value["procedure_id"])
    source_path(value["entrypoint"])
    for key in ("origin_hash", "operation_digest", "token"):
        fingerprint(value[key])
    return ChildGrant(**value)


class FamilyAdmission:
    def __init__(self, authority, catalog):
        self.authority, self.store, self.catalog = authority, authority.store, catalog
        if authority.native_children is not None:
            raise ValueError("Context already has a child admission coordinator")
        if catalog is None:
            raise ValueError("Child admission requires the approved source catalog")
        with self.store.transaction():
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS child_admissions("
                "id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,parent_id TEXT,"
                "procedure_id TEXT NOT NULL,entrypoint TEXT NOT NULL,request_id TEXT NOT NULL,"
                "origin_hash TEXT NOT NULL,operation_digest TEXT NOT NULL,token_hash TEXT NOT NULL,"
                "binding TEXT NOT NULL,state TEXT NOT NULL,"
                "UNIQUE(execution_id,request_id))"
            )
            if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 10:
                self.store.db.execute("PRAGMA user_version=10")
            self.store.db.execute(
                "UPDATE child_admissions SET state='RESTART_FENCED' WHERE state IN ('ADMITTED','CONSUMED')"
            )
        authority.native_children = self

    @staticmethod
    def origin(grant):
        value = asdict(grant)
        value.pop("token")
        return digest(value)

    def _target(self, row, path):
        source_path(path)
        if not path.endswith(".py"):
            raise Fault(403, "child_source_not_approved")
        root = self.catalog.entries.get(row["procedure_id"])
        if root is None:
            raise Fault(403, "child_source_not_approved")
        original = json.loads(root["manifest"])
        inventory = json.loads(row["inventory"])
        if (
            any(
                root[key] != inventory[key]
                for key in ("source_revision", "source_sha256", "runtime_image", "driver_binding")
            )
            or digest(original) != inventory["source_sha256"]
        ):
            raise Fault(403, "child_parent_source_binding_changed")
        for procedure, entry in self.catalog.entries.items():
            manifest = json.loads(entry["manifest"])
            if manifest["entrypoint"] != path:
                continue
            if (
                manifest["revision"] == original["revision"]
                and manifest["files"] == original["files"]
                and digest(manifest) == entry["source_sha256"]
                and entry["source_revision"] == manifest["revision"]
                and entry["runtime_image"] == root["runtime_image"]
                and entry["driver_binding"] == root["driver_binding"]
            ):
                return procedure
        raise Fault(403, "child_source_not_approved")

    def admit(self, grant, payload):
        canonical_uuid(payload["request_id"])
        if payload["parent_admission_id"] is not None:
            canonical_uuid(payload["parent_admission_id"])
        source_path(payload["entrypoint"])
        fingerprint(payload["arguments_sha256"])
        mode = payload["mode"]
        exact(mode, {"automatic", "visible", "blocking"})
        if any(type(value) is not bool for value in mode.values()):
            raise Fault(400, "invalid_child_mode")
        operation = {
            key: payload[key]
            for key in (
                "request_id",
                "parent_admission_id",
                "entrypoint",
                "arguments_sha256",
                "mode",
            )
        }
        origin, operation_hash = self.origin(grant), digest(operation)
        with self.authority._execution_lock(grant.execution_id):
            with self.store.transaction():
                row = self.authority._grant(grant)
                prior = self.store.db.execute(
                    "SELECT * FROM child_admissions WHERE execution_id=? AND request_id=?",
                    (grant.execution_id, payload["request_id"]),
                ).fetchone()
                if prior is not None:
                    if (
                        prior["operation_digest"] != operation_hash
                        or prior["origin_hash"] != origin
                    ):
                        raise Fault(409, "child_request_conflict")
                    return self._receipt(prior, replayed=True)
                procedure = self._target(row, payload["entrypoint"])
                if payload["parent_admission_id"] is not None:
                    parent = self.store.db.execute(
                        "SELECT * FROM child_admissions WHERE id=?",
                        (payload["parent_admission_id"],),
                    ).fetchone()
                    if (
                        parent is None
                        or parent["execution_id"] != grant.execution_id
                        or parent["origin_hash"] != origin
                        or parent["state"] != "CONSUMED"
                    ):
                        raise Fault(403, "child_parent_fenced")
                if (
                    self.store.db.execute("SELECT COUNT(*) FROM child_admissions").fetchone()[0]
                    >= 64
                ):
                    raise Fault(503, "child_admission_capacity")
                if self.store.db.execute(
                    "SELECT 1 FROM reservations WHERE procedure_id=?", (procedure,)
                ).fetchone():
                    raise Fault(409, "procedure_reserved")
                admission_id, token = str(uuid.uuid4()), secrets.token_hex(32)
                child = ChildGrant(
                    admission_id,
                    grant.execution_id,
                    self.store.incarnation,
                    payload["parent_admission_id"],
                    procedure,
                    payload["entrypoint"],
                    origin,
                    operation_hash,
                    token,
                )
                binding = asdict(child)
                binding.pop("token")
                try:
                    self.store.db.execute(
                        "INSERT INTO reservations VALUES(?,?)", (procedure, grant.execution_id)
                    )
                    self.store.db.execute(
                        "INSERT INTO child_admissions VALUES(?,?,?,?,?,?,?,?,?,?,'ADMITTED')",
                        (
                            admission_id,
                            grant.execution_id,
                            payload["parent_admission_id"],
                            procedure,
                            payload["entrypoint"],
                            payload["request_id"],
                            origin,
                            operation_hash,
                            secret_hash(token),
                            canonical(binding).decode(),
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    raise Fault(409, "procedure_reserved") from error
                self.store._event("NATIVE_CHILD_ADMITTED", binding)
                return dict(
                    admitted=True,
                    child_grant=asdict(child),
                    hold_retained=True,
                    native_start_qualified=False,
                    runtime_enabled=False,
                )

    def consume(self, grant, value):
        child = child_grant(value)
        binding = asdict(child)
        binding.pop("token")
        with self.authority._execution_lock(grant.execution_id):
            with self.store.transaction():
                self.authority._grant(grant)
                row = self.store.db.execute(
                    "SELECT * FROM child_admissions WHERE id=?", (child.admission_id,)
                ).fetchone()
                if (
                    row is None
                    or child.execution_id != grant.execution_id
                    or child.authority_incarnation != self.store.incarnation
                    or child.origin_hash != self.origin(grant)
                    or row["binding"] != canonical(binding).decode()
                    or not hmac.compare_digest(row["token_hash"], secret_hash(child.token))
                    or row["state"] != "ADMITTED"
                ):
                    raise Fault(403, "child_admission_fenced")
                self.store.db.execute(
                    "UPDATE child_admissions SET state='CONSUMED' WHERE id=?", (child.admission_id,)
                )
                self.store._event("NATIVE_CHILD_ADMISSION_CONSUMED", binding)
                return dict(
                    consumed=True,
                    admission_id=child.admission_id,
                    execution_id=grant.execution_id,
                    hold_retained=True,
                    native_start_qualified=False,
                    runtime_enabled=False,
                )

    @staticmethod
    def _receipt(row, *, replayed):
        # Lost delivery cannot recover plaintext authority or authorize a retry.
        return dict(
            admitted=True,
            admission_id=row["id"],
            state=row["state"],
            replayed=replayed,
            token_delivery="unavailable",
            hold_retained=True,
            native_start_qualified=False,
            runtime_enabled=False,
        )
