"""Build an explicit native profile from a prepared digest-pinned offline toolchain."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]


def validate_image(image):
    if not re.fullmatch(r"(?:[A-Za-z0-9./:_-]+@)?sha256:[0-9a-f]{64}", image):
        raise ValueError("toolchain_image_must_be_digest_pinned")
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-image", required=True)
    parser.add_argument(
        "--profile", choices=("optimized", "asan-o1", "asan-o2"), default="optimized"
    )
    args = parser.parse_args()
    validate_image(args.toolchain_image)
    folder = ROOT / ".qualification/native-build-profile" / ("run-" + uuid.uuid4().hex)
    folder.mkdir(parents=True)
    report = dict(
        schema="openbexi.native-profile-build/1",
        profile=args.profile,
        passed=False,
        full_v08_qualified=False,
        eligible_for_publication=False,
    )
    try:

        def git(*values):
            return subprocess.check_output(
                ["git", *values], cwd=ROOT, text=True
            ).strip()

        if git("status", "--porcelain", "--untracked-files=no"):
            raise ValueError("native_profile_requires_clean_sources")
        report["source_commit"] = git("rev-parse", "HEAD")
        report["source_tree"] = git("rev-parse", "HEAD^{tree}")
        epoch = git("show", "-s", "--format=%ct", "HEAD")
        report["toolchain_image"] = args.toolchain_image
        # No mutable tags, network installs or Docker cache are accepted here.
        with (folder / "build.log").open("w") as log:
            subprocess.run(
                [
                    "docker",
                    "build",
                    "--pull=false",
                    "--network=none",
                    "--no-cache",
                    "--iidfile",
                    str(folder / "image.id"),
                    "-f",
                    "host_runtime/Dockerfile.profile",
                    "--build-arg",
                    "TOOLCHAIN_IMAGE=" + args.toolchain_image,
                    "--build-arg",
                    "NATIVE_PROFILE=" + args.profile,
                    "--build-arg",
                    "SOURCE_DATE_EPOCH=" + epoch,
                    ".",
                ],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=1800,
            )
        image = (folder / "image.id").read_text().strip()
        validate_image(image)
        build = subprocess.check_output(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--entrypoint",
                "cat",
                image,
                "/opt/v08-native-home/build.json",
            ],
            text=True,
            timeout=30,
        )
        receipt = json.loads(build)
        if (
            receipt.get("native_build_profile") != args.profile
            or receipt.get("full_v08_qualified") is not False
        ):
            raise ValueError("native_build_profile_receipt_mismatch")
        (folder / "native-build.json").write_text(build)
        report.update(passed=True, image=image, source_date_epoch=int(epoch))
    except Exception as error:
        report["error_type"] = type(error).__name__
    finally:
        report["evidence_sha256"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.iterdir()
            if p.is_file()
        }
        (folder / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "output": str(folder)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
