"""Verify historical GENERIC assertions against the admitted native run and its real DSS packets."""

import base64
from collections import Counter
import gzip
import hashlib
import json

from dss.catalog import canonical
from dss.packets import decode_packet, decode_tc


GROUPS = {
    "obs": (
        "acquire",
        "described",
        "raw",
        "extended",
        "operator-eq",
        "operator-neq",
        "operator-ge",
        "operator-gt",
        "operator-le",
        "operator-lt",
        "operator-bw",
        "operator-nbw",
        "single",
        "verify-raw",
        "tolerance",
        "ignore-case",
        "result",
        "alternatives",
        "item-comparison",
        "literal-name",
    ),
    "cmd": ("build-basic", "send-name"),
}
DIMENSIONS = ("positive", "boundary", "failure", "recovery")
STAGES = ("TRANSPORT", "LOADING", "RELEASE", "ACKNOWLEDGEMENT", "ONBOARD_EXECUTION")
OUTCOMES = ("ACCEPTED", "LOADED", "RELEASED", "ACKNOWLEDGED", "SUCCEEDED")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def mapping(root, suite):
    report = json.loads(
        (root / "conformance/evidence" / (suite + ".json")).read_bytes()
    )
    for name, expected in report["inputs"].items():
        if name.startswith("conformance/" + suite + "_") and name.endswith(".py"):
            require(
                sha((root / name).read_bytes()) == expected,
                "Historical oracle source differs: " + name,
            )
    rows = {
        group + ":" + dim: report["checks"][group + ":" + dim]
        for group in GROUPS[suite]
        for dim in DIMENSIONS
    }
    for key, row in rows.items():
        require(
            row["dimension"] == key.rsplit(":", 1)[1]
            and row["passed"] is True
            and row["prompts"] == row["expected_prompts"] == [],
            "Historical case needs operator input: " + key,
        )
    return rows


def verify_simulation(folder, execution, names, *, timed_out_reads=()):
    ledger = json.loads((folder / "simulator-ledger.json").read_bytes())
    calls = json.loads((folder / "context-driver.json").read_bytes())["calls"]
    packet_file = folder / "binary-packets.json.gz"
    capture = json.loads(gzip.decompress(packet_file.read_bytes()))
    serialized = capture["packets"]
    require(
        ledger["packets"]
        == [
            {k: packet[k] for k in ("id", "topic", "sequence", "sha256")}
            for packet in serialized
        ],
        "Published packet metadata differs from the raw volume",
    )
    methods = Counter(r["path"].rsplit("/", 1)[1] for r in calls)
    failures = {event["request_id"]: event for event in timed_out_reads}
    require(
        len(failures) == len(timed_out_reads)
        and set(failures)
        == {row["request_id"] for row in calls if row["state"] != "COMPLETED"}
        and all(
            event["execution_id"] == execution
            and event["path"] == "/spell.driver.SPELLDriverInterface_TM/RefreshItem"
            and event["error_type"] == "TimeoutError"
            and event["error_chain"] == [{"type": "TimeoutError"}]
            for event in failures.values()
        ),
        "Stored read failure differs from the observed bounded telemetry timeout",
    )
    require(
        all(
            r["execution_id"] == execution
            and r["binding"] == "simulator"
            and (
                (r["state"] == "COMPLETED" and len(r["response_hash"]) == 64)
                or (
                    r["state"] == "UNCERTAIN"
                    and r["response_hash"] is None
                    and r["request_id"] in failures
                    and r["path"] == failures[r["request_id"]]["path"]
                )
            )
            for r in calls
        ),
        "A recorded driver result is incomplete or belongs to a different native execution",
    )
    acknowledgements, changes = [], set()
    for packet in serialized:
        raw = base64.b64decode(packet["base64"], validate=True)
        body = decode_packet(
            raw
        ).body  # Includes the original wire length, header and CRC checks.
        require(
            sha(raw) == packet["sha256"]
            and body["satellite_id"] == "GENERIC"
            and body["satellite_epoch"] == ledger["state"]["epoch"] == packet["epoch"]
            and body["scenario_id"] == ledger["state"]["scenario_id"],
            "DSS packet binding differs",
        )
        if packet["topic"] == "openbexi.GENERIC.ack":
            require(
                packet["sequence"] == body["ack_sequence"],
                "Acknowledgement sequence differs",
            )
            acknowledgements.append(body)
        else:
            require(
                packet["topic"] == "openbexi.GENERIC.tm"
                and packet["sequence"] == body["tm_sequence"],
                "Telemetry sequence differs",
            )
            voltage = next(
                x for x in body["items"] if x["item_id"] == "TM.POWER.BUS_VOLTAGE"
            )
            require(
                voltage["raw"]["value"] == 28000
                and voltage["engineering"]["value"] == 28.0
                and voltage["validity"] == "VALID"
                and voltage["quality"] == "GOOD",
                "Binary bus voltage differs",
            )
            if body["cause_command"]:
                changes.add((body["operation_id"], body["cause_command"]))
    operations = ledger["operations"]
    require(
        [item["ack"] for item in operations] == acknowledgements,
        "Simulator acknowledgements differ from the wire",
    )
    require(
        len(operations)
        == len(ledger["ingress"])
        == len(capture["commands"])
        == 5 * len(names),
        "Unexpected synthetic effect count",
    )
    sends = [r["request_id"] for r in calls if r["path"].endswith("/SendCommand")]
    require(
        len(sends)
        == len(set(sends))
        == len(names)
        == ledger["state"]["core"]["commands_executed"],
        "Executed command count differs from unique admitted sends",
    )
    for j, (record, ingress, packet) in enumerate(
        zip(operations, ledger["ingress"], capture["commands"])
    ):
        group, stage = divmod(j, 5)
        raw = base64.b64decode(packet["base64"], validate=True)
        command, response = decode_tc(raw), record["ack"]
        require(
            sha(raw) == record["sha256"] == packet["sha256"]
            and sha(canonical(command)) == ingress["request_hash"],
            "Command packet or canonical request digest differs",
        )
        require(
            record["rowid"] == packet["rowid"]
            and record["stage"]
            == command["stage"]
            == response["stage"]
            == ingress["stage"]
            == STAGES[stage]
            and command["operation_id"]
            == ingress["operation_id"]
            == response["operation_id"]
            == sends[group]
            and command["command_name"] == response["command_name"] == names[group]
            and command["execution_id"] == response["execution_id"] == execution
            and response["outcome"] == OUTCOMES[stage]
            and ingress["delivery_count"] == 1,
            "Ordered, single-delivery TC receipt differs",
        )
    require(
        set(zip(sends, names)) == changes,
        "Binary telemetry lost its command cause or admitted operation ID",
    )
    return {
        "context_driver_calls": dict(methods),
        "binary_packets": len(serialized),
        "ordered_stage_receipts": len(operations),
        "commands": names,
        "binary_capture_sha256": sha(packet_file.read_bytes()),
    }


def validate(root, suite, raw, identity, build, collector_sha, folder, execution):
    expected = mapping(root, suite)
    require(raw.keys() == expected.keys(), "GENERIC dimensional check set differs")
    for key, old in expected.items():
        require(
            raw[key]["source"] == old["source"]
            and raw[key]["expected_prompts"] == []
            and raw[key]["passed"] is True,
            "Unchanged native assertion failed: " + key,
        )
    selected = {k: row["source"] for k, row in expected.items()}
    expected_inputs = {
        suite + "_selected.py": sha(("SOURCES = " + repr(selected) + "\n").encode()),
        suite + "_contracts.py": sha(
            (root / "conformance" / (suite + "_contracts.py")).read_bytes()
        ),
    }
    home = "/opt/v08-native-home/bin/"
    require(
        identity["suite"] == suite
        and identity["executable_path"] == home + "SPELL-Executor"
        and identity["executable_sha256"] == build["candidate_executor_sha256"]
        and identity["build_manifest"] == build
        and identity["build_manifest_sha256"]
        == sha((json.dumps(build, indent=2) + "\n").encode())
        and identity["mapped_private_shared_libraries"]
        == [
            {
                "path": home + "libspell_executor313.so",
                "sha256": build["candidate_shared_runtime_sha256"],
            }
        ]
        and identity["oracle_inputs"] == expected_inputs
        and identity["collector_sha256"] == collector_sha
        and identity["start_ticks"] > 0
        and identity["pid"] > 0
        and identity["cwd"] == "/workspace/native-language-results",
        "Native GENERIC process identity or oracle source differs",
    )
    names = ["CMD1", "CMD1", "CMD2", "CMD1"] if suite == "cmd" else []
    physical = verify_simulation(folder, execution, names)
    if suite == "obs":
        require(
            physical["context_driver_calls"].get("RefreshItem", 0) > 0,
            "No real native telemetry reads",
        )
    return {"not_original_spelling_qualification": {}, "simulation": physical}
