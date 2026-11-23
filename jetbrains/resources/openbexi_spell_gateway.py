"""Private stdio transport for the JetBrains v0.8 tool window. Uses the installed public client."""

import json
from pathlib import Path
import sys
import uuid

from openbexi_runtime.spell_server_client import SpellServerClient, SpellServerError


def key():
    return str(uuid.uuid4())


class GatewayWorkspace:
    def __init__(self, client):
        self.client = client
        self.contexts = client.contexts()
        self.connections = {}
        self.snapshot = {}
        self.context = None

    def read(self, context):
        if context not in self.contexts:
            raise ValueError("Select an available context")
        self.snapshot = {}
        self.context = context
        health = self.client.read(context, "health")
        rows = self.client.read(context, "executions")["executions"]
        available = True
        try:
            procedures = self.client.read(context, "procedures")["procedures"]
        except SpellServerError as error:
            if error.status != 404:
                raise
            procedures, available = [], False
        permissions = set(health["permissions"])
        can_start = "execution:start" in permissions and health.get("native_launch") is True
        native_commands = set(health.get("native_commands", []))
        executions = []
        for row in rows:
            execution = row["id"]
            own = (row["owner"] == health["subject"] and "execution:control" in permissions
                   and self.client.has_controller(context, execution))
            state, life = row["control_state"], row["lifecycle"]
            terminal = row.get("native_root_result")
            commands = []
            if own and life == "STARTING" and row.get("native_root_registered") and not terminal:
                if state == "OWNED":
                    commands = sorted(native_commands)
                elif state == "HANDOFF_PAUSED" and "CMD_RUN" in native_commands:
                    commands = ["CMD_RUN"]
            executions.append({
                "id": execution, "procedure": row["procedure_id"], "owner": row["owner"],
                "control": state, "lifecycle": life, "native_result": terminal,
                "start": bool(own and can_start and available and state == "OWNED" and life == "RESERVED"
                              and not row.get("native_start_admitted") and not terminal),
                "commands": commands,
            })
        self.snapshot = {
            "subject": health["subject"], "contexts": self.contexts, "context": context,
            "procedures": procedures, "executions": executions,
            "catalog_available": available, "reserve": can_start and available,
        }
        return self.snapshot

    def handle(self, request):
        operation, context = request["operation"], request["context"]
        if operation == "refresh":
            return self.read(context)
        if context != self.context or not self.snapshot:
            raise ValueError("Refresh the current context before sending a command")
        if operation == "reserve":
            if not self.snapshot["reserve"]:
                raise ValueError("Reservation is unavailable")
            procedure = next((entry for entry in self.snapshot["procedures"]
                              if entry["procedure_id"] == request["id"]), None)
            if procedure is None:
                raise ValueError("Select an approved procedure")
            if context not in self.connections:
                self.connections[context] = self.client.authority(context, "session.open", {}, key=key())["connection_id"]
            binding = {name: procedure[name] for name in
                       ("procedure_id", "source_revision", "source_sha256", "runtime_image", "driver_binding")}
            result = self.client.authority(context, "execution.reserve",
                                           dict(binding, connection_id=self.connections[context]), key=key())
            self.client.remember_controller(context, result)
            selected = result["id"]
        else:
            selected = request["id"]
            row = next((item for item in self.snapshot["executions"] if item["id"] == selected), None)
            if row is None:
                raise ValueError("Select an execution")
            if operation == "start" and row["start"]:
                self.client.launch(context, selected, key=key())
            elif operation in row["commands"]:
                self.client.command(context, selected, operation, key=key())
            else:
                raise ValueError("Command unavailable for this execution")
        return dict(self.read(context), selected=selected)

    def close(self):
        try:
            for context, connection in self.connections.items():
                self.client.authority(context, "session.close", {"connection_id": connection}, key=key())
        finally:
            self.client.forget()


def serve(path):
    session = GatewayWorkspace(SpellServerClient.from_config(path))
    try:
        print(json.dumps({"contexts": session.contexts}), flush=True)
        while raw := sys.stdin.buffer.readline(65537):
            if len(raw) > 65536 or not raw.endswith(b"\n"):
                raise ValueError("Invalid workspace request")
            try:
                result = session.handle(json.loads(raw))
            except (ValueError, KeyError, OSError, SpellServerError) as error:
                session.snapshot = {}
                result = {"error": str(error)}
            print(json.dumps(result, allow_nan=False), flush=True)
    finally:
        session.close()


if __name__ == "__main__":
    try:
        serve(Path(sys.argv[1]))
    except (ValueError, KeyError, OSError, SpellServerError) as error:
        print(json.dumps({"error": str(error)}), flush=True)
        raise SystemExit(1)
