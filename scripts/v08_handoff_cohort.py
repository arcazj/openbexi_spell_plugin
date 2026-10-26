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
        "from spell.lang.functions import StartProc,Send,Prompt\n"
        "from spell.lang.constants import YES_NO\n"
        "from spell.lang.modifiers import Type\n"
        "assert Send(command='CMD1',Timeout=3,HandleError=False,PromptUser=False,Confirm=False) is True\n"
        "threading.Thread(target=progress,args=('handoff-background',),daemon=True).start()\n"
        "assert StartProc('handoff_child',Automatic=True,Visible=True,Blocking=False,HandleError=False) is True\n"
        "from openbexi_dss_proxy import connection\n"
        "from openbexi_dss_proxy.tc import TC,descriptor\n"
        "from spell.stubs import SPELLDriver_pb2 as proto\n"
        "import grpc\n"
        "with open('/control/handoff-epoch') as f:old_epoch=f.read()\n"
        "old_packet=descriptor(TC._createTcItem('CMD1'),{'Timeout':3}).SerializeToString()\n"
        "count=0\n"
        "prompted=False\n"
        "while not os.path.exists('/control/handoff-after'):\n"
        "    if not prompted and os.path.exists('/control/handoff-prompt'):\n"
        "        assert Prompt('HANDOFF_NATIVE_PROMPT',{Type:YES_NO}) is True\n"
        "        with open('/workspace/handoff-prompt-answered','w') as f:f.write('answered')\n"
        "        prompted=True\n"
        "    count+=1\n"
        "    with open('/workspace/handoff-root.next','w') as f:f.write(str(count))\n"
        "    os.replace('/workspace/handoff-root.next','/workspace/handoff-root')\n"
        "    time.sleep(0.02)\n"
        "try:\n"
        "    connection.channel.unary_unary('/spell.driver.SPELLDriverInterface_TC/SendCommand')(old_packet,metadata=(('x-openbexi-runtime-epoch',old_epoch),),timeout=3)\n"
        "except grpc.RpcError:\n"
        "    with open('/workspace/handoff-stale-denied','w') as f:f.write('denied')\n"
        "else:raise AssertionError('Delayed old-owner driver operation accepted')\n"
        # Send the exact same valid payload as a fresh original-driver call
        # under B. A malformed delayed packet must not pass this negative test.
        "assert connection.call('TC','SendCommand',proto.CommandDesc.FromString(old_packet)).value is True\n"
        "with open('/control/handoff-epoch') as f:b_epoch=f.read()\n"
        "with open('/workspace/handoff-after','w') as f:f.write('completed')\n"
        "returned=False\n"
        "reconnected=False\n"
        "disconnected_probed=False\n"
        "while not os.path.exists('/control/handoff-finish'):\n"
        "    count+=1\n"
        "    with open('/workspace/handoff-root.next','w') as f:f.write(str(count))\n"
        "    os.replace('/workspace/handoff-root.next','/workspace/handoff-root')\n"
        "    if not returned and os.path.exists('/control/handoff-return'):\n"
        "        try:\n"
        "            connection.channel.unary_unary('/spell.driver.SPELLDriverInterface_TC/SendCommand')(old_packet,metadata=(('x-openbexi-runtime-epoch',b_epoch),),timeout=3)\n"
        "        except grpc.RpcError:\n"
        "            with open('/workspace/handoff-stale-b-denied','w') as f:f.write('denied')\n"
        "        else:raise AssertionError('Delayed B driver operation accepted after return')\n"
        "        assert connection.call('TC','SendCommand',proto.CommandDesc.FromString(old_packet)).value is True\n"
        "        with open('/control/handoff-epoch') as f:a_epoch=f.read()\n"
        "        with open('/workspace/handoff-return','w') as f:f.write('completed')\n"
        "        returned=True\n"
        "    if returned and not disconnected_probed and os.path.exists('/control/handoff-disconnected'):\n"
        "        try:\n"
        "            connection.channel.unary_unary('/spell.driver.SPELLDriverInterface_TC/SendCommand')(old_packet,metadata=(('x-openbexi-runtime-epoch',a_epoch),),timeout=3)\n"
        "        except grpc.RpcError:\n"
        "            with open('/workspace/handoff-disconnected-denied','w') as f:f.write('denied')\n"
        "        else:raise AssertionError('Disconnected controller driver operation accepted')\n"
        "        disconnected_probed=True\n"
        "    if returned and not reconnected and os.path.exists('/control/handoff-reconnect'):\n"
        "        try:\n"
        "            connection.channel.unary_unary('/spell.driver.SPELLDriverInterface_TC/SendCommand')(old_packet,metadata=(('x-openbexi-runtime-epoch',a_epoch),),timeout=3)\n"
        "        except grpc.RpcError:\n"
        "            with open('/workspace/handoff-stale-connection-denied','w') as f:f.write('denied')\n"
        "        else:raise AssertionError('Old connection packet accepted after same-epoch reconnect')\n"
        "        assert connection.call('TC','SendCommand',proto.CommandDesc.FromString(old_packet)).value is True\n"
        "        with open('/workspace/handoff-reconnected','w') as f:f.write('completed')\n"
        "        reconnected=True\n"
        "    time.sleep(0.02)\n"
    )


def drain_agent_before_freeze(command, name, control, await_event, *, rotation):
    """Host requests transport idle, separately from its mandatory cgroup proof."""
    epoch = (control / "handoff-epoch").read_text()
    marker = control / "handoff-prepare.next"
    marker.write_text(epoch)
    marker.replace(control / "handoff-prepare")
    await_event([name], "native-handoff-agent-drained", seconds=15, minimum=rotation)
    events = [
        json.loads(line)
        for line in command("docker", "logs", name).splitlines()
        if line.startswith('{"event": "native-handoff-agent-drained"')
    ]
    if (
        len(events) != rotation
        or events[-1]["runtime_epoch"] != epoch
        or events[-1]["active_calls"] != 0
        or events[-1]["quiescence_proven"] is not False
    ):
        raise RuntimeError("Agent drain acknowledgement differs from this freeze")


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
    info = json.loads(command("docker", "inspect", name))[0]
    if not info["State"]["Running"] or info["State"]["Pid"] <= 0:
        raise RuntimeError("Counter observation requires the live bound container")
    # The workspace is a private tmpfs. Read its actual mounted namespace via
    # the host's /proc root; never exec or temporarily thaw a frozen container.
    result = json.loads(
        command(
            "sudo",
            "-n",
            "python3",
            "-c",
            "import json,sys;from pathlib import Path;"
            "root=Path('/proc')/sys.argv[1]/'root/workspace';"
            "print(json.dumps({k:int((root/('handoff-'+k)).read_text()) for k in ('root','background','child')}))",
            str(info["State"]["Pid"]),
        )
    )
    with (directory / "handoff-counter-observations.jsonl").open("a") as output:
        output.write(json.dumps(result) + "\n")
    return result


def qualify_reconnect(
    *,
    name,
    controller,
    proof,
    handoff_call,
    command,
    control,
    handles,
    original,
    output,
    await_event,
):
    """Actual disconnect keeps the family alive; same-owner resume needs host proof."""
    eid, epoch, generation = (
        proof["execution_id"],
        proof["expected_epoch"],
        proof["connection_generation"],
    )
    loss = controller.lose(proof["connection_id"])
    lost_at = time.monotonic()

    def view():
        return next(
            e
            for e in controller("execution.list", {}, subject="observer")["executions"]
            if e["id"] == eid
        )

    disconnected = view()
    while (
        disconnected["control_state"] == "OWNED"
        and time.monotonic() - lost_at < loss["lease_seconds"] + 3
    ):
        time.sleep(0.1)
        disconnected = view()
    detected_after = time.monotonic() - lost_at
    if (
        disconnected["owner"],
        disconnected["epoch"],
        disconnected["control_state"],
    ) != ("alice", epoch, "CONTROLLER_DISCONNECTED"):
        raise RuntimeError("Disconnected controller authority was not fenced")
    if disconnected["pause_barrier"]["quiescence_proven"]:
        raise RuntimeError("Disconnect falsely claimed whole-family pause")
    before = counters(command, name, output)
    (control / "handoff-disconnected").write_text(
        "automatic controller lease fence observed"
    )
    await_event([name], "native-handoff-disconnected-denied", seconds=15)
    time.sleep(3)
    alive = counters(command, name, output)
    if any(alive[k] <= before[k] for k in before):
        raise RuntimeError(
            "Controller disconnect stopped an original native participant"
        )
    for fd in handles.values():
        if select.select([fd], [], [], 0)[0]:
            raise RuntimeError("Controller disconnect terminated an original process")
    try:
        controller("execution.command", dict(proof, command="CMD_RUN"))
    except Fault as error:
        if error.status != 403:
            raise
    else:
        raise RuntimeError("Disconnected controller command was accepted")
    connection = controller("session.open", {})["connection_id"]
    request = dict(execution_id=eid, connection_id=connection, expected_epoch=epoch)
    pending = controller("execution.rebind", request)
    if not pending.get("rebind_pending") or "capability" in pending:
        raise RuntimeError("Native reconnect granted control before host freeze")
    drain_agent_before_freeze(command, name, control, await_event, rotation=3)
    command("docker", "pause", name)
    state = handoff_call("status")
    evidence = frozen_evidence(command, name, state, handles, original)
    frozen = counters(command, name, output)
    time.sleep(3)
    if counters(command, name, output) != frozen:
        raise RuntimeError("Native reconnect family advanced while frozen")
    completed = handoff_call(
        "complete", barrier_id=pending["barrier_id"], evidence=evidence
    )
    paused = view()
    if (
        not completed["quiescence_proven"]
        or not completed["connection_rebound"]
        or completed["effective_transfer"]
        or (
            paused["owner"],
            paused["epoch"],
            paused["connection_generation"],
            paused["control_state"],
        )
        != ("alice", epoch, generation + 1, "HANDOFF_PAUSED")
    ):
        raise RuntimeError(
            "Same-owner reconnect changed ownership or omitted the pause barrier"
        )
    bound = controller("execution.rebind", request)
    new_proof = dict(
        execution_id=eid,
        connection_id=connection,
        expected_epoch=epoch,
        connection_generation=bound["connection_generation"],
        capability=bound["capability"],
        target_admission_id=None,
    )
    resume = controller("execution.command", dict(new_proof, command="CMD_RUN"))
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
    await_event([name], "native-handoff-activated", seconds=15, minimum=3)
    (control / "handoff-reconnect").write_text("explicit same-owner resume")
    await_event([name], "native-handoff-reconnected", seconds=25)
    after = counters(command, name, output)
    if any(after[k] <= frozen[k] for k in frozen):
        raise RuntimeError("Reconnected original family did not continue")
    active = view()
    if (
        active["owner"],
        active["epoch"],
        active["connection_generation"],
        active["control_state"],
    ) != ("alice", epoch, generation + 1, "OWNED"):
        raise RuntimeError(
            "Observer did not see same-owner explicit native continuation"
        )
    try:
        controller("execution.command", dict(proof, command="CMD_RUN"))
    except Fault as error:
        if error.status != 403:
            raise
    else:
        raise RuntimeError("Old controller capability revived after reconnect")
    return dict(
        passed=True,
        automatic_disconnect_detection=True,
        explicit_close_sent=False,
        controller_loss=loss,
        detection_seconds=detected_after,
        owner_unchanged=True,
        epoch_unchanged=True,
        epoch=epoch,
        previous_connection_generation=generation,
        connection_generation=generation + 1,
        disconnect_observation_seconds=3,
        counters_before_disconnect=before,
        counters_after_disconnect=alive,
        frozen_observation_seconds=3,
        frozen_counters=frozen,
        counters_after_resume=after,
        original_processes=len(handles),
        original_processes_survived_disconnect=True,
        disconnected_native_packet_denied=True,
        old_connection_native_packet_denied=True,
        old_controller_capability_denied=True,
        fresh_same_epoch_driver_command_completed=True,
        quiescence_claimed_on_disconnect=False,
        effective_transfer=False,
        public_launch_enabled=False,
        full_recovery_qualified=False,
    )


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
    verify_step=False,
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

    def prompt_snapshot():
        with closing(
            sqlite3.connect(
                "file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True
            )
        ) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM native_prompts WHERE execution_id=?", (execution["id"],)
            ).fetchall()
            if len(rows) != 1:
                raise RuntimeError(
                    "Handoff requires exactly one original native prompt"
                )
            return dict(rows[0])

    (control / "handoff-prompt").write_text("open untimed native prompt")
    await_event([name], "native-handoff-prompt-open", seconds=15)
    pending_prompt = prompt_snapshot()
    if (
        pending_prompt["state"],
        pending_prompt["outcome"],
        pending_prompt["handoff_untimed"],
    ) != ("OPEN", None, 1):
        raise RuntimeError("Native handoff prompt is not unanswered and untimed")

    def prompt_reply(authority_proof, subject):
        return controller(
            "execution.prompt.reply",
            dict(
                authority_proof,
                prompt_id=pending_prompt["prompt_id"],
                target_admission_id=None,
                definition_sha256=pending_prompt["definition_hash"],
                action="ANSWER",
                answer="0",
            ),
            subject=subject,
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
        drain_agent_before_freeze(command, name, control, await_event, rotation=1)
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
        if prompt_snapshot() != pending_prompt:
            raise RuntimeError("Host freeze changed the original prompt identity")
        for subject, authority_proof in (
            ("alice", proof),
            ("observer", bproof),
            ("bob", bproof),
        ):
            try:
                prompt_reply(authority_proof, subject)
            except Fault as error:
                if error.status != 403:
                    raise
            else:
                raise RuntimeError("Prompt answered before explicit new-owner resume")
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
        if prompt_snapshot() != pending_prompt:
            raise RuntimeError("Runtime rotation changed the original pending prompt")
        for subject in ("alice", "observer"):
            try:
                prompt_reply(proof, subject)
            except Fault as error:
                if error.status != 403:
                    raise
            else:
                raise RuntimeError(
                    "Former owner or observer answered transferred prompt"
                )
        prompt_reply(bproof, "bob")
        await_event([name], "native-handoff-prompt-answered", seconds=15)
        if prompt_snapshot() != dict(
            pending_prompt, state="CLOSED", outcome="ANSWER_SELECTED"
        ):
            raise RuntimeError(
                "New owner did not close the exact original native prompt"
            )
        with closing(
            sqlite3.connect(
                "file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True
            )
        ) as db:
            replies = db.execute(
                "SELECT owner,epoch,connection_id,connection_generation,state FROM native_prompt_replies WHERE prompt_id=?",
                (pending_prompt["prompt_id"],),
            ).fetchall()
        if replies != [
            ("bob", 2, bob, bproof["connection_generation"], "CONSUMED_UNPROVEN")
        ]:
            raise RuntimeError(
                "Transferred prompt reply lost fresh controller provenance"
            )
        # B exercises the original native owner-command path after the family
        # resume. C keeps observing; A's pending STEP must stay fenced.
        operations = (
            ("CMD_PAUSE", "CMD_STEP", "CMD_RUN")
            if verify_step
            else ("CMD_PAUSE", "CMD_RUN")
        )
        for operation in operations:
            if operation == "CMD_STEP":
                (control / "handoff-step-requested").write_text("explicit B step")
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
            if operation == "CMD_STEP":
                await_event([name], "native-handoff-stepped", seconds=15)
        (control / "handoff-after").write_text("B continuation")
        await_event([name], "native-handoff-continued", seconds=25)
        continued = next(
            e
            for e in controller("execution.list", {}, subject="observer")["executions"]
            if e["id"] == execution["id"]
        )
        if (continued["owner"], continued["epoch"], continued["control_state"]) != (
            "bob",
            2,
            "OWNED",
        ) or not continued["pause_barrier"]["runtime_identity_rotated"]:
            raise RuntimeError("C did not observe B's resumed original family")
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
        # Transfer the same sealed family back to A. No first-round host proof,
        # controller grant or captured B packet can authorize this new epoch.
        claim_back = controller(
            "execution.claim",
            dict(
                execution_id=execution["id"], connection_id=connection, expected_epoch=2
            ),
            subject="alice",
        )
        accepted_back = controller(
            "execution.decide",
            dict(
                {k: v for k, v in bproof.items() if k != "target_admission_id"},
                claim_id=claim_back["claim_id"],
                decision="accept",
            ),
            subject="bob",
        )
        drain_agent_before_freeze(command, name, control, await_event, rotation=2)
        command("docker", "pause", name)
        return_state = handoff_call("status")
        return_evidence = frozen_evidence(
            command, name, return_state, handles, original
        )
        second_before = counters(command, name, output)
        time.sleep(3)
        if counters(command, name, output) != second_before:
            raise RuntimeError("Original family advanced during second freeze")
        try:
            handoff_call(
                "complete", barrier_id=accepted["barrier_id"], evidence=evidence
            )
        except Fault as error:
            if error.status != 403:
                raise
        else:
            raise RuntimeError("First-round host proof replayed during second transfer")
        handoff_call(
            "complete", barrier_id=accepted_back["barrier_id"], evidence=return_evidence
        )
        for former_subject, former_proof in (("alice", proof), ("bob", bproof)):
            try:
                controller(
                    "execution.command",
                    dict(former_proof, target_admission_id=None, command="CMD_RUN"),
                    subject=former_subject,
                )
            except Fault as error:
                if error.status != 403:
                    raise
            else:
                raise RuntimeError(
                    "Earlier controller proof survived the second transfer"
                )
        rebound = controller(
            "execution.rebind",
            dict(
                execution_id=execution["id"], connection_id=connection, expected_epoch=3
            ),
            subject="alice",
        )
        aproof = dict(
            execution_id=execution["id"],
            connection_id=connection,
            expected_epoch=3,
            connection_generation=rebound["connection_generation"],
            capability=rebound["capability"],
            target_admission_id=None,
        )
        resume_back = controller(
            "execution.command", dict(aproof, command="CMD_RUN"), subject="alice"
        )
        permission_back = handoff_call(
            "resume",
            barrier_id=accepted_back["barrier_id"],
            resume_id=resume_back["command_id"],
            evidence=return_evidence,
        )
        temporary.write_text(permission_back["runtime_epoch"])
        temporary.replace(control / "handoff-epoch")
        command("docker", "unpause", name)
        await_event([name], "native-handoff-activated", seconds=15, minimum=2)
        (control / "handoff-return").write_text("explicit return to A")
        await_event([name], "native-handoff-returned", seconds=25)
        returned = next(
            e
            for e in controller("execution.list", {}, subject="observer")["executions"]
            if e["id"] == execution["id"]
        )
        if (returned["owner"], returned["epoch"], returned["control_state"]) != (
            "alice",
            3,
            "OWNED",
        ):
            raise RuntimeError("Observer did not see resumed A at the third epoch")
        second_after = counters(command, name, output)
        if any(second_after[k] <= second_before[k] for k in second_before):
            raise RuntimeError("Original family did not advance after return to A")
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
            history = db.execute(
                "SELECT COUNT(*) FROM live_handoff_history WHERE execution_id=?",
                (execution["id"],),
            ).fetchone()[0]
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
            or len(ctx) != 15
            or any(r[5] != "ACKED" for r in ctx)
            or {json.loads(r[3])["control_epoch"] for r in ctx} != {1, 2, 3}
            or delayed != ("DELIVERY_FENCED",)
            or holds != 3
            or history != 1
        ):
            raise RuntimeError(
                "Cross-owner DSS receipts, delayed STEP fence or holds differ"
            )
        reconnection = qualify_reconnect(
            name=name,
            controller=controller,
            proof=aproof,
            handoff_call=handoff_call,
            command=command,
            control=control,
            handles=handles,
            original=original,
            output=output,
            await_event=await_event,
        )
        with closing(
            sqlite3.connect(
                "file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True
            )
        ) as db:
            ctx = db.execute(
                "SELECT * FROM effect_intents ORDER BY operation,stage"
            ).fetchall()
            history = db.execute(
                "SELECT COUNT(*) FROM live_handoff_history WHERE execution_id=?",
                (execution["id"],),
            ).fetchone()[0]
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
            or len(ctx) != 20
            or any(r[5] != "ACKED" for r in ctx)
            or {json.loads(r[3])["control_epoch"] for r in ctx} != {1, 2, 3}
            or {json.loads(r[3])["connection_generation"] for r in ctx} != {1, 2, 3, 4}
            or history != 2
        ):
            raise RuntimeError(
                "Same-epoch reconnect lost independent effect provenance"
            )
        (control / "handoff-finish").write_text("finish after B effects")
        await_event([name], "native-handoff-finished", seconds=25)
        fence = host_call(
            "begin", container_id=original["Id"], native_status="FINISHED"
        )
        if fence["state"] != "FENCED" or not fence["hold_retained"]:
            raise RuntimeError("Finished handoff family lacks a terminal fence")
        (control / "handoff-cleanup").write_text("host terminal fence committed")
        if command("docker", "wait", name, timeout=20) != "0":
            raise RuntimeError("Native handoff cleanup failed")
        stopped = json.loads(command("docker", "inspect", name))[0]
        from v08_terminal_cohort import validate_stopped

        validate_stopped(stopped, original["Id"], worker_image)
        if any(not select.select([fd], [], [], 0)[0] for fd in handles.values()):
            raise RuntimeError("Original handoff participant survived cleanup")
        settled = host_call(
            "complete",
            challenge=fence["challenge"],
            evidence=dict(
                provider="docker-pidfd-terminal/1",
                container_id=stopped["Id"],
                image=stopped["Image"],
                running=stopped["State"]["Running"],
                pid=stopped["State"]["Pid"],
                exit_code=stopped["State"]["ExitCode"],
                oom_killed=stopped["State"]["OOMKilled"],
                restart_count=stopped["RestartCount"],
                original_handles=len(handles),
                exited_handles=len(handles),
                roster_hash=fence["roster_hash"],
            ),
        )
        if settled["state"] != "SETTLED" or settled["report"]["effect_receipts"] != 20:
            raise RuntimeError(
                "Cross-owner terminal settlement failed: " + json.dumps(settled)
            )
        released = host_call(
            "release", challenge=fence["challenge"], report_hash=settled["report_hash"]
        )
        with closing(
            sqlite3.connect(
                "file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True
            )
        ) as db:
            remaining = db.execute("SELECT execution_id FROM reservations").fetchall()
            spent = db.execute("SELECT SUM(spent) FROM workers").fetchone()[0]
        if (
            released["state"] != "RELEASED"
            or len(remaining) != 1
            or remaining[0][0] == execution["id"]
            or spent != 1
        ):
            raise RuntimeError(
                "Handoff settlement changed unrelated holds or worker reuse"
            )
        report["native_live_handoff"] = dict(
            passed=True,
            open_prompt_handoff=dict(
                passed=True,
                scope="unanswered exact-zero-timeout native prompt",
                original_prompt_id=pending_prompt["prompt_id"],
                original_definition_sha256=pending_prompt["definition_hash"],
                original_member_binding_hash=pending_prompt["member_hash"],
                original_family_origin_hash=pending_prompt["origin_hash"],
                identity_preserved=True,
                former_owner_and_observer_denied=True,
                reply_before_explicit_resume_denied=True,
                reply_owner="bob",
                reply_epoch=2,
                reply_connection_generation=bproof["connection_generation"],
                native_outcome="ANSWER_SELECTED",
                selected_answers=1,
                timed_prompt_transfer_qualified=False,
                queued_or_uncertain_reply_transfer_qualified=False,
            ),
            native_step_location_verified=verify_step,
            provider="docker-cgroup-freezer-pidfd/1",
            whole_family_paused=True,
            frozen_observation_seconds=3,
            root_child_background_counters_before=first,
            root_child_background_counters_after=after,
            original_processes=len(handles),
            replacement_native_processes=False,
            old_owner_denied=True,
            observer_read_only=True,
            observer_saw_paused_and_resumed_b=True,
            owner="alice",
            epoch=3,
            accepted_transfers=2,
            same_owner_reconnections=1,
            native_reconnect=reconnection,
            completed_transfer_history=history,
            first_round_host_proof_replay_denied=True,
            previous_b_controller_and_native_packet_denied=True,
            second_frozen_observation_seconds=3,
            second_counters_before=second_before,
            second_counters_after=second_after,
            new_owner_native_commands=3 if verify_step else 2,
            stale_native_driver_denied=True,
            delayed_old_owner_step_fenced=True,
            dss_commands=4,
            matching_stage_receipts=20,
            provenance_epochs=[1, 2, 3],
            provenance_connection_generations=[1, 2, 3, 4],
            logical_reservations_during_handoff=holds,
            terminal_settlement=released,
            original_processes_exited=True,
            unrelated_reservations_retained=len(remaining),
            worker_reusable=False,
            new_children_after_handoff=False,
            full_v08_qualified=False,
        )
    finally:
        for fd in handles.values():
            os.close(fd)
        # A failure never resumes frozen code for cleanup. Docker kill/remove
        # in the enclosing host teardown remains the only failure cleanup path.
