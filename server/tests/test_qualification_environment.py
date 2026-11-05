"""Environment receipts cannot leak ambient credentials or silently replace evidence."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "qualification_environment_test", ROOT / "scripts/record_qualification_environment.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_receipt_filters_docker_and_environment_credentials(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "private-test-token")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")

    def command(args):
        if args[0] == "docker":
            return {
                "exit_code": 0,
                "stdout": json.dumps(
                    {
                        "NCPU": 8,
                        "MemTotal": 123456,
                        "HttpProxy": "private-proxy-password",
                        "RegistryConfig": {"credential": "private-registry-token"},
                    }
                ),
            }
        return {"exit_code": 0, "stdout": ""}

    monkeypatch.setattr(module, "command", command)
    result = module.collect(ROOT, "test")
    encoded = json.dumps(result)
    assert "private-test-token" not in encoded
    assert "private-proxy-password" not in encoded
    assert "private-registry-token" not in encoded
    assert result["ci"]["GITHUB_RUN_ID"] == "123"
    assert result["docker"]["NCPU"] == 8
    assert result["qualification_pass"] is False


def test_unavailable_git_status_is_unknown_not_clean(monkeypatch):
    monkeypatch.setattr(module, "command", lambda args: {"error": "FileNotFoundError"})
    result = module.collect(ROOT, "missing-tools")
    assert result["working_tree_dirty"] is None
    assert result["docker"] == {"error": "FileNotFoundError"}
    assert result["git_head"] == {"error": "FileNotFoundError"}


def test_existing_evidence_is_not_overwritten(tmp_path, monkeypatch):
    output = tmp_path / "environment.json"
    original = b'{"existing": "immutable"}\n'
    output.write_bytes(original)
    monkeypatch.setattr(sys, "argv", ["record", "--profile", "test", "--output", str(output)])
    monkeypatch.setattr(module, "collect", lambda root, profile: {"replacement": True})
    with pytest.raises(FileExistsError):
        module.main()
    assert output.read_bytes() == original
