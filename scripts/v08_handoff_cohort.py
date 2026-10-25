"""Independent host cgroup freezer and A/B/C native handoff acceptance."""

from contextlib import closing
import json
import os
import select
import sqlite3
import time

from openbexi_spell_server.contracts import Fault


def handoff_fixture(*, child=False):
    progress = (
        "def progress(name,count=0):\n"
        "    while not os.path.exists('/control/handoff-finish'):\n"
        "        count+=1\n"
        "        with open('/workspace/'+name+'.next','w') as f:f.write(str(count))\n"
        "        os.replace('/workspace/'+name+'.next','/workspace/'+name)\n"
        "        time.sleep(0.02)\n"
    )
    prefix = "import os,time,threading\n" + progress
    if child:
        return prefix + "progress('handoff-child')\n"
    return prefix + (
        "from spell.lang.functions import StartProc,Send\n"
        "assert Send(command='CMD1',Timeout=3,HandleError=False,PromptUser=False,Confirm=False) is True\n"
        "threading.Thread(target=progress,args=('handoff-background',),daemon=True).start()\n"
        "assert StartProc('handoff_child',Automatic=True,Visible=True,Blocking=False,HandleError=False) is True\n"
        "from openbexi_dss_proxy import connection\n"
        "from spell.stubs import SPELLDriver_pb2 as proto\n"
        "import grpc\n"
        "with open('/control/handoff-epoch') as f:old_epoch=f.read()\n"
        "old_packet=proto.CommandDesc(command=proto.TcItemDesc(mnemonic='CMD1')).SerializeToString()\n"
        "count=0\n"
        "while not os.path.exists('/control/handoff-after'):\n"
        "    count+=1\n"
        "    with open('/workspace/handoff-root.next','w') as f:f.write(str(count))\n"
        "    os.replace('/workspace/handoff-root.next','/workspace/handoff-root')\n"
        "    time.sleep(0.02)\n"
        "try:\n"
        "    connection.channel.unary_unary('/spell.driver.SPELLDriverInterface_TC/SendCommand')(old_packet,metadata=(('x-openbexi-runtime-epoch',old_epoch),),timeout=3)\n"
        "except grpc.RpcError:\n"
        "    with open('/workspace/handoff-stale-denied','w') as f:f.write('denied')\n"
        "else:raise AssertionError('Delayed old-owner driver operation accepted')\n"
        "assert Send(command='CMD1',Timeout=3,HandleError=False,PromptUser=False,Confirm=False) is True\n"
        "with open('/workspace/handoff-after','w') as f:f.write('completed')\n"
        "progress('handoff-root',count)\n"
    )


def frozen_evidence(command, name, state, handles, original):
    info = json.loads(command("docker", "inspect", name))[0]
    if (
        info["Id"] != original["Id"]
        or info["Image"] != original["Image"]
        or not info["State"]["Paused"]
        or not info["State"]["Running"]
    ):
        raise RuntimeError(
            "Native family container is not the original paused container"
        )
    # Read the kernel's cgroup-v2 completion indication from the actual bound
    # container init PID. Docker's Paused Boolean alone is insufficient.
    program = """import json,sys,hashlib
from pathlib import Path
pid=sys.argv[1];root=Path('/proc')/pid
rows=(root/'cgroup').read_text().splitlines()
assert len(rows)==1 and rows[0].startswith('0::/')
cgroup=Path('/sys/fs/cgroup')/rows[0][3:].lstrip('/')
events=dict(line.split() for line in (cgroup/'cgroup.events').read_text().splitlines())
assert events['frozen']=='1'
members=json.loads(sys.argv[2]);tasks=[int(p) for p in (cgroup/'cgroup.procs').read_text().split()]
found=[]
for member in members:
 matches=[]
 for hostpid in tasks:
  p=Path('/proc')/str(hostpid)
  status=dict(line.split(':',1) for line in (p/'status').read_text().splitlines() if ':' in line)
  if int(status['NSpid'].split()[-1])==member['pid']:
   stat=(p/'stat').read_text();start=int(stat[stat.rfind(')')+2:].split()[19])
   assert start==member['start_ticks']
   assert hashlib.sha256((p/'exe').read_bytes()).hexdigest()==member['executable_sha256']
   matches.append(hostpid)
 assert len(matches)==1
 found.append(member['binding_hash'])
print(json.dumps({'frozen':True,'member_bindings':sorted(found),'pids':sorted(tasks)}))
"""
    actual = json.loads(
        command(
            "sudo",
            "-n",
            "python3",
            "-c",
            program,
            str(info["State"]["Pid"]),
            json.dumps(state["members"]),
        )
    )
    # Original pidfds remain live; never treat a recycled numeric PID as proof.
    if set(actual["pids"]) != set(handles):
        raise RuntimeError("Container process roster changed before freezer completion")
    for fd in handles.values():
        poller = select.poll()
        poller.register(fd, select.POLLIN)
        if poller.poll(0):
            raise RuntimeError("Original native participant exited")
    return dict(
        provider="docker-cgroup-freezer-pidfd/1",
        container_id=info["Id"],
        image=info["Image"],
        paused=True,
        running=True,
        frozen=actual["frozen"],
        oom_killed=info["State"]["OOMKilled"],
        restart_count=info["RestartCount"],
        original_handles=len(handles),
        alive_handles=len(handles),
        member_bindings=actual["member_bindings"],
        roster_hash=state["roster_hash"],
    )


def counters(command, name, directory):
    result = {}
    for label in ("root", "background", "child"):
        target = directory / ("read-" + label)
        command("docker", "cp", name + ":/workspace/handoff-" + label, str(target))
        result[label] = int(target.read_text())
    return result


def qualify_handoff_case(
    *,
    name,
    execution,
    connection,
    controller,
    state,
    worker_image,
    command,
    control,
    await_event,
    report,
    host_call,
    handoff_call,
    output,
):
    await_event([name], "native-handoff-ready", seconds=45)
    initial = controller("execution.list", {}, subject="observer")
    original = json.loads(command("docker", "inspect", name))[0]
    handles = {}
    for row in command("docker", "top", name, "-eo", "pid").splitlines()[1:]:
        pid = int(row.strip())
        handles[pid] = os.pidfd_open(pid)
    proof = dict(
        execution_id=execution["id"],
        connection_id=connection,
        expected_epoch=execution["epoch"],
        connection_generation=execution["connection_generation"],
        capability=execution["capability"],
    )
    bob = controller("session.open", {}, subject="bob")["connection_id"]
    queued = controller(
        "execution.command", dict(proof, target_admission_id=None, command="CMD_STEP")
    )
    claim = controller(
        "execution.claim",
        dict(execution_id=execution["id"], connection_id=bob, expected_epoch=1),
        subject="bob",
    )
    if (
        next(
            e
            for e in controller("execution.list", {}, subject="observer")["executions"]
            if e["id"] == execution["id"]
        )["owner"]
        != "alice"
    ):
        raise RuntimeError("Claim bypassed A acceptance")
    try:
        accepted = controller(
            "execution.decide",
            dict(proof, claim_id=claim["claim_id"], decision="accept"),
        )
        command("docker", "pause", name)
        host_state = handoff_call("status")
        evidence = frozen_evidence(command, name, host_state, handles, original)
        first = counters(command, name, output)
        time.sleep(3)
        if counters(command, name, output) != first or min(first.values()) < 1:
            raise RuntimeError(
                "Native root, child or background thread advanced while frozen"
            )
        completed = handoff_call(
            "complete", barrier_id=accepted["barrier_id"], evidence=evidence
        )
        if not completed["quiescence_proven"] or not completed["effective_transfer"]:
            raise RuntimeError("Host-proven family did not transfer while paused")
        if (
            handoff_call(
                "complete", barrier_id=accepted["barrier_id"], evidence=evidence
            )
            != completed
        ):
            raise RuntimeError("Host handoff exact replay differs")
        view = controller("execution.list", {}, subject="observer")
        changed = next(e for e in view["executions"] if e["id"] == execution["id"])
        if (
            changed["owner"] != "bob"
            or changed["epoch"] != 2
            or changed["control_state"] != "HANDOFF_PAUSED"
        ):
            raise RuntimeError("C did not observe atomic B ownership")
        if [e for e in initial["executions"] if e["id"] != execution["id"]] != [
            e for e in view["executions"] if e["id"] != execution["id"]
        ]:
            raise RuntimeError("Handoff changed an unrelated reservation")
        for subject in ("alice", "observer"):
            try:
                controller(
                    "execution.command",
                    dict(proof, target_admission_id=None, command="CMD_RUN"),
                    subject=subject,
                )
            except Fault as error:
                if error.status != 403:
                    raise
            else:
                raise RuntimeError("Former owner or observer mutated the family")
        bound = controller(
            "execution.rebind",
            dict(execution_id=execution["id"], connection_id=bob, expected_epoch=2),
            subject="bob",
        )
        bproof = dict(
            execution_id=execution["id"],
            connection_id=bob,
            expected_epoch=2,
            connection_generation=bound["connection_generation"],
            capability=bound["capability"],
            target_admission_id=None,
        )
        resume = controller(
            "execution.command", dict(bproof, command="CMD_RUN"), subject="bob"
        )
        evidence = frozen_evidence(command, name, host_state, handles, original)
        permission = handoff_call(
            "resume",
            barrier_id=accepted["barrier_id"],
            resume_id=resume["command_id"],
            evidence=evidence,
        )
        temporary = control / "handoff-epoch.next"
        temporary.write_text(permission["runtime_epoch"])
        temporary.replace(control / "handoff-epoch")
        command("docker", "unpause", name)
        await_event([name], "native-handoff-activated", seconds=15)
        # B exercises the original native owner-command path after the family
        # resume. C keeps observing; A's pending STEP must stay fenced.
        for operation in ("CMD_PAUSE", "CMD_RUN"):
            result = controller(
                "execution.command", dict(bproof, command=operation), subject="bob"
            )
            until = time.monotonic() + 15
            while True:
                with closing(
                    sqlite3.connect(
                        "file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True
                    )
                ) as db:
                    seen = db.execute(
                        "SELECT d.disposition FROM native_owner_command_dispositions d WHERE d.command_id=?",
                        (result["command_id"],),
                    ).fetchone()
                if seen == ("HANDLER_RETURNED",):
                    break
                if time.monotonic() > until:
                    raise RuntimeError("B native command did not return")
                time.sleep(0.05)
            if operation == "CMD_PAUSE":
                await_event([name], "native-handoff-paused", seconds=15)
        (control / "handoff-after").write_text("B continuation")
        await_event([name], "native-handoff-continued", seconds=25)
        after = counters(command, name, output)
        if any(after[k] <= first[k] for k in first):
            raise RuntimeError("Original family did not continue after B resume")
        current = json.loads(command("docker", "inspect", name))[0]
        if current["Id"] != original["Id"] or current["Image"] != worker_image:
            raise RuntimeError("Native family container was replaced")
        for fd in handles.values():
            poller = select.poll()
            poller.register(fd, select.POLLIN)
            if poller.poll(0):
                raise RuntimeError("Handoff replaced an original process")
        with closing(
            sqlite3.connect(
                "file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True
            )
        ) as db:
            ctx = db.execute(
                "SELECT * FROM effect_intents ORDER BY operation,stage"
            ).fetchall()
            delayed = db.execute(
                "SELECT state FROM native_owner_commands WHERE command_id=?",
                (queued["command_id"],),
            ).fetchone()
            holds = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        with closing(
            sqlite3.connect(
                "file:" + str(state / "driver/driver.sqlite3") + "?mode=ro", uri=True
            )
        ) as db:
            drv = db.execute(
                "SELECT * FROM effect_intents ORDER BY operation,stage"
            ).fetchall()
        if (
            ctx != drv
            or len(ctx) != 10
            or any(r[5] != "ACKED" for r in ctx)
            or {json.loads(r[3])["control_epoch"] for r in ctx} != {1, 2}
            or delayed != ("DELIVERY_FENCED",)
            or holds != 3
        ):
            raise RuntimeError(
                "Cross-owner DSS receipts, delayed STEP fence or holds differ"
            )
        (control / "handoff-finish").write_text("finish after B effects")
        await_event([name], "native-handoff-finished", seconds=25)
        if command("docker", "wait", name, timeout=20) != "0":
            raise RuntimeError("Native handoff cleanup failed")
        report["native_live_handoff"] = dict(
            passed=True,
            provider="docker-cgroup-freezer-pidfd/1",
            whole_family_paused=True,
            frozen_observation_seconds=3,
            root_child_background_counters_before=first,
            root_child_background_counters_after=after,
            original_processes=len(handles),
            replacement_native_processes=False,
            old_owner_denied=True,
            observer_read_only=True,
            owner="bob",
            epoch=2,
            new_owner_native_commands=2,
            stale_native_driver_denied=True,
            delayed_old_owner_step_fenced=True,
            dss_commands=2,
            matching_stage_receipts=10,
            provenance_epochs=[1, 2],
            logical_reservations_retained=holds,
            worker_reusable=False,
            new_children_after_handoff=False,
            full_v08_qualified=False,
        )
    finally:
        for fd in handles.values():
            os.close(fd)
        # A failure never resumes frozen code for cleanup. Docker kill/remove
        # in the enclosing host teardown remains the only failure cleanup path.
