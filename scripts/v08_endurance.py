"""Bounded original-family endurance exercises, separate from release receipts."""

import json
import hashlib
from pathlib import Path
import re
import select
import time

from openbexi_spell_server.contracts import Fault


def kernel_oom_observations(raw, original_pids, earliest_ns, latest_ns):
    """Only original PIDs in this liveness interval; no unrelated kernel logs."""
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("kernel_observation_read_bound_exceeded")
    pattern = re.compile(
        r"^\[\s*(\d+)\.(\d{1,9})\]\s+"
        r"(?:Out of memory|Memory cgroup out of memory): Killed process "
        r"(\d+) \(([A-Za-z0-9_.-]{1,32})\) total-vm:(\d+)kB, "
        r"anon-rss:(\d+)kB, file-rss:(\d+)kB, shmem-rss:(\d+)kB, "
        r"UID:(\d+) pgtables:(\d+)kB oom_score_adj:(-?\d+)$"
    )
    events = []
    for line in raw.splitlines():
        match = pattern.fullmatch(line)
        if not match:
            continue
        stamp = int(match[1]) * 10**9 + int(match[2].ljust(9, "0"))
        pid = int(match[3])
        if pid not in original_pids or not earliest_ns <= stamp <= latest_ns:
            continue
        events.append(
            {
                "kernel_boot_ns": stamp,
                "host_pid": pid,
                "program": match[4],
                "total_vm_bytes": int(match[5]) * 1024,
                "anonymous_rss_bytes": int(match[6]) * 1024,
                "file_rss_bytes": int(match[7]) * 1024,
                "shared_memory_rss_bytes": int(match[8]) * 1024,
                "uid": int(match[9]),
                "pagetable_bytes": int(match[10]) * 1024,
                "oom_score_adj": int(match[11]),
                "matched_kernel_line": line,
            }
        )
    return events


def process_failure_observation(handles, original, *, command=None, earliest_ns=0):
    """Observe the already-held original pidfds; never infer identity from PID reuse."""
    began = time.monotonic_ns()
    processes = [
        {"host_pid": pid, "pidfd_exited": bool(select.select([fd], [], [], 0)[0])}
        for pid, fd in sorted(handles.items())
    ]
    result = {
        "schema": "openbexi.native-endurance-process-failure/1",
        "observation_start_ns": began,
        "observation_end_ns": time.monotonic_ns(),
        "container_id": original["Id"],
        "original_container_host_pid": original["State"]["Pid"],
        "expected_processes": 8,
        "observed_processes": len(handles),
        "processes": processes,
        "observations_atomic": False,
        "kernel_victim_pid_observed": False,
        "oom_cause_inferred": False,
    }
    if command is not None:
        # Ubuntu 24.04's util-linux 2.39 rejects --time-format raw. The default
        # format is already seconds since boot; disable only terminal colors.
        # Retain the query's numeric outcome without unrelated kernel contents.
        query = ("sudo", "-n", "dmesg", "--color=never")
        result["kernel_query"] = list(query)
        result["kernel_query_start_ns"] = time.monotonic_ns()
        try:
            raw = command(*query, timeout=10)
            result["kernel_query_end_ns"] = time.monotonic_ns()
            result["kernel_query_returncode"] = 0
            events = kernel_oom_observations(
                raw, set(handles), earliest_ns, result["kernel_query_end_ns"]
            )
            result["kernel_events"] = events
            result["kernel_victim_pid_observed"] = bool(events)
            result["kernel_output_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
            result["kernel_clock"] = (
                "dmesg default boot timestamp; numeric interval retained"
            )
        except Exception as error:
            result["kernel_observation_error"] = type(error).__name__
            result["kernel_query_end_ns"] = time.monotonic_ns()
            returncode = getattr(error, "returncode", None)
            if type(returncode) is int:
                result["kernel_query_returncode"] = returncode
    return result


def latency_summary(values):
    if not values:
        return {"available": False, "samples": 0}
    ordered = sorted(values)

    def percentile(fraction):
        index = (len(ordered) - 1) * fraction
        left = int(index)
        return ordered[left] + (
            ordered[min(left + 1, len(ordered) - 1)] - ordered[left]
        ) * (index - left)

    return dict(
        available=True,
        samples=len(values),
        p50_ms=percentile(0.5),
        p95_ms=percentile(0.95),
        p99_ms=percentile(0.99),
        maximum_ms=max(values),
    )


def run_soak(
    *,
    duration,
    name,
    controller,
    proof,
    bob_connection,
    handoff_call,
    command,
    control,
    handles,
    original,
    output,
    await_event,
):
    """One family, six total transfers and two reconnects including the prelude.

    Three prelude rotations plus five here equals the existing runtime cap of
    eight. No limit is raised. Controller proofs stay in memory, never receipts.
    """
    if duration != 3600:
        raise ValueError("endurance_requires_3600_seconds")
    from v08_handoff_cohort import counters, drain_agent_before_freeze, frozen_evidence

    started = time.monotonic_ns()
    current_proof = dict(proof)
    connections = {"alice": proof["connection_id"], "bob": bob_connection}
    rotation = 3
    extra_transfers = extra_reconnections = 0
    latencies = []
    transitions = []
    previous_liveness = None
    liveness_check_started = None
    observation_error = None
    output = Path(output)
    first = previous = counters(command, name, output)

    def rpc(operation, params, subject="alice"):
        began = time.monotonic_ns()
        try:
            return controller(operation, params, subject=subject)
        finally:
            elapsed = (time.monotonic_ns() - began) / 1e6
            latencies.append(elapsed)
            with (output / "endurance-rpc-latency.jsonl").open("a") as stream:
                stream.write(
                    json.dumps({"operation": operation, "milliseconds": elapsed}) + "\n"
                )

    def view():
        return next(
            e
            for e in rpc("execution.list", {}, "observer")["executions"]
            if e["id"] == current_proof["execution_id"]
        )

    def deny(stale, subject):
        try:
            rpc("execution.command", dict(stale, command="CMD_RUN"), subject)
        except Fault as error:
            if error.status != 403:
                raise
        else:
            raise RuntimeError("endurance_stale_controller_accepted")

    def liveness():
        nonlocal previous_liveness, liveness_check_started
        liveness_check_started = time.monotonic_ns()
        if len(handles) != 8 or any(
            select.select([fd], [], [], 0)[0] for fd in handles.values()
        ):
            raise RuntimeError("endurance_original_process_exited")
        previous_liveness = {
            "start_ns": liveness_check_started,
            "end_ns": time.monotonic_ns(),
        }

    def complete_and_resume(
        pending, request, subject, stale, old_subject, expected_epoch
    ):
        nonlocal rotation, current_proof
        rotation += 1
        if rotation > 8:
            raise RuntimeError("endurance_rotation_budget_exceeded")
        drain_agent_before_freeze(
            command, name, control, await_event, rotation=rotation
        )
        command("docker", "pause", name)
        state = handoff_call("status")
        evidence = frozen_evidence(command, name, state, handles, original)
        before = counters(command, name, output)
        time.sleep(3)
        if counters(command, name, output) != before:
            raise RuntimeError("endurance_advanced_while_frozen")
        handoff_call("complete", barrier_id=pending["barrier_id"], evidence=evidence)
        deny(stale, old_subject)
        bound = rpc("execution.rebind", request, subject)
        current_proof = dict(
            execution_id=request["execution_id"],
            connection_id=request["connection_id"],
            expected_epoch=expected_epoch,
            connection_generation=bound["connection_generation"],
            capability=bound["capability"],
            target_admission_id=None,
        )
        resume = rpc(
            "execution.command", dict(current_proof, command="CMD_RUN"), subject
        )
        permission = handoff_call(
            "resume",
            barrier_id=pending["barrier_id"],
            resume_id=resume["command_id"],
            evidence=evidence,
        )
        marker = control / "handoff-epoch.next"
        marker.write_text(permission["runtime_epoch"])
        marker.replace(control / "handoff-epoch")
        command("docker", "unpause", name)
        await_event([name], "native-handoff-activated", seconds=15, minimum=rotation)
        time.sleep(3)
        after = counters(command, name, output)
        if any(after[k] <= before[k] for k in before):
            raise RuntimeError("endurance_no_progress_after_resume")
        observed = view()
        if (
            observed["owner"],
            observed["epoch"],
            observed["control_state"],
            observed["connection_generation"],
        ) != (subject, expected_epoch, "OWNED", current_proof["connection_generation"]):
            raise RuntimeError("endurance_observer_state_differs")
        deny(stale, old_subject)
        liveness()

    def transfer(subject, recipient):
        nonlocal extra_transfers
        start = time.monotonic_ns()
        stale = dict(current_proof)
        epoch = stale["expected_epoch"]
        claim = rpc(
            "execution.claim",
            dict(
                execution_id=stale["execution_id"],
                connection_id=connections[recipient],
                expected_epoch=epoch,
            ),
            recipient,
        )
        accepted = rpc(
            "execution.decide",
            dict(
                {k: v for k, v in stale.items() if k != "target_admission_id"},
                claim_id=claim["claim_id"],
                decision="accept",
            ),
            subject,
        )
        request = dict(
            execution_id=stale["execution_id"],
            connection_id=connections[recipient],
            expected_epoch=epoch + 1,
        )
        complete_and_resume(accepted, request, recipient, stale, subject, epoch + 1)
        extra_transfers += 1
        transitions.append(
            dict(
                kind="transfer",
                owner=recipient,
                epoch=epoch + 1,
                elapsed_seconds=(time.monotonic_ns() - start) / 1e9,
                stale_proof_denied=True,
            )
        )

    def reconnect():
        nonlocal extra_reconnections
        start = time.monotonic_ns()
        stale = dict(current_proof)
        epoch, generation = stale["expected_epoch"], stale["connection_generation"]
        loss = controller.lose(stale["connection_id"])
        deadline = time.monotonic() + loss["lease_seconds"] + 10
        observed = view()
        while observed["control_state"] == "OWNED" and time.monotonic() < deadline:
            time.sleep(0.1)
            observed = view()
        if (observed["owner"], observed["epoch"], observed["control_state"]) != (
            "alice",
            epoch,
            "CONTROLLER_DISCONNECTED",
        ):
            raise RuntimeError("endurance_controller_loss_unfenced")
        if observed["pause_barrier"]["quiescence_proven"]:
            raise RuntimeError("endurance_false_quiescence_on_disconnect")
        deny(stale, "alice")
        connections["alice"] = rpc("session.open", {})["connection_id"]
        request = dict(
            execution_id=stale["execution_id"],
            connection_id=connections["alice"],
            expected_epoch=epoch,
        )
        pending = rpc("execution.rebind", request)
        if not pending.get("rebind_pending") or "capability" in pending:
            raise RuntimeError("endurance_premature_reconnect_authority")
        complete_and_resume(pending, request, "alice", stale, "alice", epoch)
        if current_proof["connection_generation"] != generation + 1:
            raise RuntimeError("endurance_reconnect_generation_differs")
        extra_reconnections += 1
        transitions.append(
            dict(
                kind="reconnect",
                owner="alice",
                epoch=epoch,
                elapsed_seconds=(time.monotonic_ns() - start) / 1e9,
                stale_proof_denied=True,
            )
        )

    failure = None
    try:
        next_stage = 0
        while time.monotonic_ns() - started < duration * 10**9:
            elapsed = (time.monotonic_ns() - started) / 1e9
            if next_stage < 2 and elapsed >= (next_stage + 1) * 1200:
                transfer("alice", "bob")
                transfer("bob", "alice")
                if next_stage == 0:
                    reconnect()
                next_stage += 1
            time.sleep(5)
            current = counters(command, name, output)
            if any(current[k] <= previous[k] for k in previous):
                raise RuntimeError("endurance_original_family_stopped_advancing")
            previous = current
            liveness()
        if extra_transfers != 4 or extra_reconnections != 1 or rotation != 8:
            raise RuntimeError("endurance_cycles_incomplete")
    except BaseException as error:
        failure = type(error).__name__
        try:
            observation = process_failure_observation(
                handles,
                original,
                command=command,
                earliest_ns=previous_liveness["start_ns"]
                if previous_liveness
                else started,
            )
            observation["previous_successful_liveness"] = previous_liveness
            observation["latest_liveness_check_started_ns"] = liveness_check_started
            observation["failure_type"] = failure
            (output / "endurance-process-failure.json").write_text(
                json.dumps(observation, indent=2) + "\n"
            )
        except Exception as evidence_error:
            # Evidence failure cannot conceal or replace the original failure.
            observation_error = type(evidence_error).__name__
        raise
    finally:
        # No capabilities, connection IDs or runtime tokens in the public receipt.
        summary = dict(
            schema="openbexi.native-endurance-cycles/1",
            passed=failure is None,
            failure=failure,
            process_failure_observation_error=observation_error,
            full_v08_qualified=False,
            extra_transfers=extra_transfers,
            extra_reconnections=extra_reconnections,
            rotations=rotation,
            transitions=transitions,
            rpc_latency=latency_summary(latencies),
            latency_slo_qualified=False,
        )
        (output / "endurance-cycles.json").write_text(
            json.dumps(summary, indent=2) + "\n"
        )
    return dict(
        start_ns=started,
        end_ns=time.monotonic_ns(),
        minimum_seconds=duration,
        counters_before=first,
        counters_after=previous,
        original_processes=len(handles),
        all_intervals_advanced=True,
        extra_transfers=extra_transfers,
        extra_reconnections=extra_reconnections,
        final_owner="alice",
        final_epoch=current_proof["expected_epoch"],
        extra_history_entries=rotation - 3,
    )
