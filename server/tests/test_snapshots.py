import copy
import os

import pytest

from openbexi_spell_server.contracts import Fault, digest
from openbexi_spell_server.snapshots import (
    SnapshotCatalog,
    git_manifest,
    validate_manifest,
    verify_directory,
)


from conftest import git, commit


def reservation(source, *, procedure="procedure", connection="unused"):
    entry = source["config"]["procedure"]
    return dict(
        procedure_id=procedure,
        connection_id=connection,
        source_revision=source["revision"],
        source_sha256=digest(source["manifest"]),
        runtime_image=entry["runtime_image"],
        driver_binding=entry["driver_binding"],
    )


def test_exact_git_objects_and_exported_source_match_without_execution(source):
    assert verify_directory(source["directory"], source["manifest"]) == digest(source["manifest"])
    (source["root"] / "main.py").write_text("raise RuntimeError('uncommitted modification')\n")
    assert git_manifest(source["root"], source["revision"], "main.py") == source["manifest"]
    second = commit(source["root"])
    git(source["root"], "replace", source["revision"], second)
    assert git_manifest(source["root"], source["revision"], "main.py") == source["manifest"]


@pytest.mark.parametrize(
    "change",
    ["modified", "missing", "extra", "mode", "symlink", "directory_link", "hardlink", "fifo"],
)
def test_worker_inventory_denies_changed_or_unsafe_source(source, change):
    directory = source["directory"]
    main = directory / "main.py"
    if change == "modified":
        main.write_text("changed")
    elif change == "missing":
        main.unlink()
    elif change == "extra":
        (directory / "extra.py").write_text("extra")
    elif change == "mode":
        main.chmod(0o755)
    elif change == "symlink":
        main.unlink()
        main.symlink_to(source["root"] / "main.py")
    elif change == "directory_link":
        (directory / "lib/helper.py").unlink()
        (directory / "lib").rmdir()
        (directory / "lib").symlink_to(source["root"] / "lib")
    elif change == "hardlink":
        os.link(main, directory / "extra.py")
    else:
        os.mkfifo(directory / "extra.pipe")
    with pytest.raises(Fault):
        verify_directory(directory, source["manifest"])


def test_root_symlink_and_unbounded_empty_directory_trees_are_denied(source, tmp_path):
    alias = tmp_path / "root-link"
    alias.symlink_to(source["directory"], target_is_directory=True)
    with pytest.raises(Fault, match="unsafe_source_object"):
        verify_directory(alias, source["manifest"])
    with pytest.raises(Fault, match="unsafe_source_object"):
        verify_directory(source["directory"] / ".." / source["directory"].name, source["manifest"])
    parent_alias = tmp_path / "parent-link"
    parent_alias.symlink_to(source["directory"].parent, target_is_directory=True)
    with pytest.raises(Fault, match="unsafe_source_object"):
        verify_directory(parent_alias / source["directory"].name, source["manifest"])
    for n in range(257):
        (source["directory"] / ("dir-" + str(n))).mkdir()
    with pytest.raises(Fault, match="source_inventory_limit"):
        verify_directory(source["directory"], source["manifest"])


def test_catalog_aliases_share_one_logical_identity_and_bind_approved_metadata(source):
    catalog = SnapshotCatalog(source["config"])
    assert catalog.approve(reservation(source, procedure="alias"))["procedure_id"] == "procedure"
    for key, value in (
        ("procedure_id", "forged"),
        ("source_revision", "0" * 40),
        ("source_sha256", "0" * 64),
        ("runtime_image", "sha256:" + "0" * 64),
        ("driver_binding", "other"),
    ):
        with pytest.raises(Fault):
            catalog.approve({**reservation(source), key: value})
    conflicting = copy.deepcopy(source["config"])
    conflicting["other"] = {**conflicting["procedure"], "aliases": []}
    with pytest.raises(ValueError, match="two logical identities"):
        SnapshotCatalog(conflicting)


def test_approved_child_catalog_can_exceed_worker_count_but_has_a_retained_bound(source):
    for index in range(11):
        (source["root"] / f"child{index}.py").write_text("RESULT=42\n")
    revision = commit(source["root"])
    template = source["config"]["procedure"]
    config = {
        f"child-{index}": dict(
            template, revision=revision, entrypoint=f"child{index}.py", aliases=[]
        )
        for index in range(11)
    }
    assert len(SnapshotCatalog(config).entries) == 11
    with pytest.raises(ValueError):
        SnapshotCatalog({f"procedure-{index}": config["child-0"] for index in range(65)})


@pytest.mark.parametrize("object_kind", ["symlink", "submodule", "large", "many"])
def test_git_inventory_rejects_unsupported_objects_and_limits(source, object_kind):
    root = source["root"]
    if object_kind == "symlink":
        (root / "alias.py").symlink_to("main.py")
    elif object_kind == "submodule":
        git(
            root,
            "update-index",
            "--add",
            "--cacheinfo",
            "160000," + source["revision"] + ",dependency",
        )
    elif object_kind == "large":
        (root / "big.py").write_bytes(b"x" * 65537)
    else:
        for n in range(65):
            (root / ("file-" + str(n) + ".py")).write_text("x")
    revision = commit(root, stage=object_kind != "submodule")
    with pytest.raises(Fault):
        git_manifest(root, revision, "main.py")


@pytest.mark.parametrize(
    "change",
    ["duplicate", "traversal", "absolute", "boolean_size", "unknown", "missing_entrypoint"],
)
def test_manifest_is_strict_and_cannot_redirect_filesystem_reads(source, change):
    manifest = copy.deepcopy(source["manifest"])
    if change == "duplicate":
        manifest["files"].append(manifest["files"][0])
    elif change in ("traversal", "absolute"):
        manifest["files"][0]["path"] = "../secret" if change == "traversal" else "/secret"
    elif change == "boolean_size":
        manifest["files"][0]["bytes"] = True
    elif change == "unknown":
        manifest["url"] = "https://invalid"
    else:
        manifest["entrypoint"] = "unknown.py"
    with pytest.raises(Fault):
        validate_manifest(manifest)


def test_partial_clone_is_rejected_before_any_object_fetch(source):
    git(source["root"], "config", "remote.origin.promisor", "true")
    git(source["root"], "config", "remote.origin.url", "https://example.invalid/never-fetch")
    with pytest.raises(Fault, match="partial_clone_not_supported"):
        git_manifest(source["root"], source["revision"], "main.py")
