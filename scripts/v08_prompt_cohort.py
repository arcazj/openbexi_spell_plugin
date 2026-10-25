"""Original-native prompts across root/child members; never transfer approval.

The host reads its own private authority database only to observe the exact
native prompt identities. Answers still enter through the real authenticated
owner RPC, worker delivery, pinned Executor callback and final native selection.
"""

from contextlib import closing
import sqlite3
import threading
import time
import uuid

from openbexi_spell_server.contracts import Fault


def prompt_fixture(*, timeout=False):
    return (
        "from spell.lang.functions import Prompt\n"
        "from spell.lang.constants import YES_NO\n"
        "from spell.lang.modifiers import Type,Default,Timeout\n"
        "assert Prompt('STEP1_NATIVE_PROMPT', {Type:YES_NO"
        + (",Default:True,Timeout:1" if timeout else "")
        + "}) is True\n"
    )


class PromptCohort:
    def __init__(self, state, controller, executions, connection):
        self.database = state / "context.sqlite3"
        self.controller, self.connection = controller, connection
        self.executions = {row["id"]: row for row in executions}
        self.timeout_execution = executions[0]["id"]
        self.stop = threading.Event()
        self.error = None
        self.replied = set()
        self.negatives = 0
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()

    def run(self):
        try:
            deadline = time.monotonic() + 150
            while not self.stop.is_set():
                if time.monotonic() >= deadline:
                    raise TimeoutError("Native prompt cohort observation expired")
                with closing(sqlite3.connect(self.database)) as db:
                    db.row_factory = sqlite3.Row
                    rows = db.execute("SELECT * FROM native_prompts").fetchall()
                for row in rows:
                    if row["state"] != "OPEN" or row["prompt_id"] in self.replied:
                        continue
                    # Exactly one root has a native timed default. No owner
                    # response is injected for that generation.
                    if (
                        row["execution_id"] == self.timeout_execution
                        and not row["target_id"]
                    ):
                        continue
                    owner = self.executions[row["execution_id"]]
                    proof = dict(
                        execution_id=owner["id"],
                        connection_id=self.connection,
                        expected_epoch=owner["epoch"],
                        connection_generation=owner["connection_generation"],
                        capability=owner["capability"],
                        prompt_id=row["prompt_id"],
                        target_admission_id=row["target_id"] or None,
                        definition_sha256=row["definition_hash"],
                        action="ANSWER",
                        answer="0",
                    )
                    # Native raw YES_NO replies are option indices, not Python
                    # booleans or textual answers. Unknown ownership is denied.
                    if not self.negatives:
                        for changed in (
                            dict(proof, expected_epoch=owner["epoch"] + 1),
                            dict(proof, prompt_id=str(uuid.uuid4())),
                            dict(proof, definition_sha256="0" * 64),
                        ):
                            try:
                                self.controller("execution.prompt.reply", changed)
                            except Fault as error:
                                if error.status not in (403, 409):
                                    raise
                                self.negatives += 1
                            else:
                                raise RuntimeError(
                                    "Invalid owner prompt request was accepted"
                                )
                    self.replied.add(row["prompt_id"])
                    result = self.controller("execution.prompt.reply", proof)
                    if result.get("state") != "QUEUED":
                        raise RuntimeError("Native prompt owner admission differs")
                time.sleep(0.03)
        except BaseException as error:
            self.error = error
            self.stop.set()

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=8)
        if self.thread.is_alive():
            raise RuntimeError("Native prompt host thread failed to settle")
        if self.error is not None:
            raise RuntimeError("Native prompt cohort failed") from self.error
        with closing(sqlite3.connect(self.database)) as db:
            prompts = db.execute(
                "SELECT state,outcome,COUNT(*) FROM native_prompts GROUP BY state,outcome"
            ).fetchall()
            replies = db.execute(
                "SELECT state,COUNT(*) FROM native_prompt_replies GROUP BY state"
            ).fetchall()
        if prompts != [("CLOSED", "ANSWER_SELECTED", 20), ("CLOSED", "TIMEOUT", 1)]:
            raise RuntimeError(
                "Original native prompt outcomes differ: " + str(prompts)
            )
        if (
            replies != [("CONSUMED_UNPROVEN", 20)]
            or len(self.replied) != 20
            or self.negatives != 3
        ):
            raise RuntimeError("Native prompt final consumption evidence differs")
        return dict(
            passed=True,
            actual_native_executor=True,
            prompt_generations=21,
            owner_answers_selected=20,
            native_timed_defaults=1,
            invalid_owner_denials=3,
            root_child_and_grandchild=True,
            reply_grants_consumed_once=True,
            quiescence_proven=False,
            effective_transfer=False,
            full_v08_qualified=False,
        )
