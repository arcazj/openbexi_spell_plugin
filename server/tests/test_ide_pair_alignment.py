"""Keep installed-client identity checks and actual CI checkouts in agreement."""

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_joint_qualification_checkouts_match_installed_client_identity():
    pair = json.loads((ROOT / "docs/v0.8/IDE_PAIR.json").read_text())
    checkouts = []
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        checkouts.extend(
            (path.name, match)
            for match in re.findall(
                r"repository: arcazj/openbexi_ide\s+ref: ([0-9a-f]{40})\b",
                path.read_text(),
            )
        )
    assert checkouts, "joint qualification must check out an immutable companion"
    assert all(commit == pair["ide_commit"] for _, commit in checkouts), checkouts
