"""Evidence-only development Python supply-chain checks. Never a v0.8 release gate.

Read independently produced SBOM/audit artifacts and validate installed wheel
identity, license metadata, package scope and absence of bundled PEM private keys.
A successful Python-only scan cannot qualify native C/C++ binaries, OS image,
full SBOM/license review or independent security acceptance.
"""

import argparse
from datetime import datetime, timezone
from email import message_from_bytes
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import zipfile


PRIVATE = re.compile(
    rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
)


def assess(root, wheel_path, sbom_path, audit_path):
    root = Path(root).resolve()
    wheel = Path(wheel_path).resolve()
    sbom = json.loads(Path(sbom_path).read_text())
    audit = json.loads(Path(audit_path).read_text())
    expected_version = tomllib.loads((root / "server/pyproject.toml").read_text())[
        "project"
    ]["version"]
    result = dict(
        schema="openbexi.v08.supply-chain-component/1",
        recorded_at=datetime.now(timezone.utc).isoformat(),
        checked_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=root
        ).strip(),
        wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
        sbom_sha256=hashlib.sha256(Path(sbom_path).read_bytes()).hexdigest(),
        audit_sha256=hashlib.sha256(Path(audit_path).read_bytes()).hexdigest(),
        python=sys.version.split()[0],
        full_v08_qualified=False,
        independent_security_qualified=False,
        package_version=expected_version,
    )
    if wheel.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Wheel exceeds accepted development size")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if not any(".dist-info/licenses/LICENSE" in name for name in names):
            raise ValueError("Installed package lacks an SPDX license file")
        if not any(name.startswith("openbexi_spell_server/") for name in names):
            raise ValueError("Development service package is missing")
        if any(".." in Path(name).parts or name.startswith("/") for name in names):
            raise ValueError("Wheel path traversal")
        if any(PRIVATE.search(archive.read(name)) for name in names):
            raise ValueError("Wheel embeds private PEM key material")
        metadata_paths = [
            name for name in names if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_paths) != 1:
            raise ValueError("Wheel package identity is missing or ambiguous")
        metadata = message_from_bytes(archive.read(metadata_paths[0]))
        if (
            metadata.get("Name") != "openbexi-spell-server"
            or metadata.get("Version") != expected_version
        ):
            raise ValueError("Wheel version differs from the candidate source")
        result["wheel_file_count"] = len(names)
    if sbom.get("bomFormat") != "CycloneDX" or not sbom.get("components"):
        raise ValueError("CycloneDX SBOM or component inventory missing")
    components = sbom["components"]
    matches = [x for x in components if x.get("name") == "openbexi-spell-server"]
    if len(matches) != 1 or matches[0].get("version") != expected_version:
        raise ValueError("SBOM is not for the candidate server version")
    result["sbom_components"] = len(components)
    dependencies = audit.get("dependencies")
    if type(dependencies) is not list or not dependencies:
        raise ValueError("Real vulnerability audit dependency inventory missing")
    audited_server = [
        item for item in dependencies if item.get("name") == "openbexi-spell-server"
    ]
    if len(audited_server) != 1 or audited_server[0].get("version") != expected_version:
        raise ValueError("Vulnerability audit is not for the candidate server version")
    result["unaudited_dependencies"] = [
        {"name": item["name"], "reason": item["skip_reason"]}
        for item in dependencies
        if item.get("skip_reason")
    ]
    affected = sorted(
        (item.get("name", "<unreported>"), item.get("version", "<unreported>"))
        for item in dependencies
        if item.get("vulns")
    )
    result["audited_dependencies"] = len(dependencies)
    result["known_vulnerable_dependencies"] = [
        {"name": name, "version": version} for name, version in affected
    ]
    result["passed"] = not affected
    result["scope"] = "development installed Python package only"
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--wheel", type=Path, required=True)
    p.add_argument("--sbom", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    report = assess(a.root, a.wheel, a.sbom, a.audit)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "scope": report["scope"],
                "audited_dependencies": report["audited_dependencies"],
                "known_vulnerable_dependencies": report[
                    "known_vulnerable_dependencies"
                ],
                "full_v08_qualified": False,
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
