"""Hosted prompt oracle must use original admissions, not guess native # suffixes."""

import importlib.util
from pathlib import Path
import sqlite3

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "v08_prompt_lookup", ROOT / "scripts/v08_native_prompts.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def database():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        "CREATE TABLE native_prompts(prompt_id TEXT,execution_id TEXT,target_id TEXT,"
        "instance_id TEXT,origin_hash TEXT,member_hash TEXT,state TEXT);"
        "CREATE TABLE native_members(execution_id TEXT,target_id TEXT,instance_id TEXT,"
        "origin_hash TEXT,binding_hash TEXT,state TEXT);"
        "CREATE TABLE child_admissions(id TEXT,execution_id TEXT,origin_hash TEXT,"
        "parent_id TEXT,state TEXT,entrypoint TEXT);"
    )
    try:
        yield db
    finally:
        db.close()


def member(db, suffix="0", *, target="child", prompt="prompt", execution="execution"):
    native = "prompt_child#" + suffix if target else "prompt_complete#1"
    db.execute(
        "INSERT INTO native_prompts VALUES(?,?,?,?,?,?,?)",
        (prompt, execution, target, native, "origin", "binding", "OPEN"),
    )
    db.execute(
        "INSERT INTO native_members VALUES(?,?,?,?,?,?)",
        (execution, target, native, "origin", "binding", "REGISTERED_UNPROVEN"),
    )
    if target:
        db.execute(
            "INSERT INTO child_admissions VALUES(?,?,?,?,?,?)",
            (target, execution, "origin", None, "CONSUMED", "prompt_child.py"),
        )
    return native


@pytest.mark.parametrize("suffix", ["0", "1", "7", "123"])
def test_child_prompt_resolves_exact_original_binding_not_assumed_suffix(database, suffix):
    native = member(database, suffix)
    answer = module.select_pending_prompt(database, "execution", child_entrypoint="prompt_child.py")
    assert answer["instance_id"] == native
    assert answer["target_id"] == "child" and answer["prompt_id"] == "prompt"
    assert (
        module.select_pending_prompt(database, "foreign", child_entrypoint="prompt_child.py")
        is None
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE child_admissions SET entrypoint='foreign.py'",
        "UPDATE child_admissions SET execution_id='foreign'",
        "UPDATE child_admissions SET id='foreign'",
        "UPDATE child_admissions SET origin_hash='foreign'",
        "UPDATE child_admissions SET state='ADMITTED'",
        "UPDATE child_admissions SET parent_id='other-child'",
        "UPDATE native_members SET binding_hash='foreign'",
        "UPDATE native_members SET instance_id='foreign#0'",
        "UPDATE native_members SET origin_hash='foreign'",
        "UPDATE native_members SET state='RESTART_FENCED'",
        "UPDATE native_prompts SET state='CLOSED'",
        "UPDATE native_prompts SET target_id='foreign'",
        "DELETE FROM native_members",
        "DELETE FROM child_admissions",
    ],
)
def test_incomplete_foreign_restarted_or_unconsumed_binding_is_not_selected(database, mutation):
    member(database)
    database.execute(mutation)
    assert (
        module.select_pending_prompt(database, "execution", child_entrypoint="prompt_child.py")
        is None
    )


def test_closed_seen_prompt_and_wrong_root_are_not_selected(database):
    member(database, target="")
    assert (
        module.select_pending_prompt(database, "execution", instance="prompt_complete#1")[
            "prompt_id"
        ]
        == "prompt"
    )
    assert (
        module.select_pending_prompt(
            database, "execution", instance="prompt_complete#1", exclude=["prompt"]
        )
        is None
    )
    assert module.select_pending_prompt(database, "execution", instance="prompt_complete#0") is None
    assert (
        module.select_pending_prompt(database, "execution", child_entrypoint="prompt_child.py")
        is None
    )


def test_ambiguous_children_cannot_make_qualifier_choose_arbitrarily(database):
    member(database)
    member(database, "1", target="child-two", prompt="prompt-two")
    with pytest.raises(RuntimeError, match="multiple pending"):
        module.select_pending_prompt(database, "execution", child_entrypoint="prompt_child.py")


def test_only_one_root_or_child_selector_can_be_supplied(database):
    for params in ({}, {"instance": "root#1", "child_entrypoint": "prompt_child.py"}):
        with pytest.raises(ValueError, match="one exact root or admitted child"):
            module.select_pending_prompt(database, "execution", **params)
