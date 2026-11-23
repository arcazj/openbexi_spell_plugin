"""Install the exact wheel identified in IDE_PAIR.json and retain its pip receipt."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def build_pinned_wheel(checkout, commit, directory):
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
    ).strip()
    if head != commit:
        raise ValueError(f"Companion checkout is {head}, expected {commit}")
    epoch = subprocess.check_output(
        ["git", "show", "-s", "--format=%ct", commit], cwd=checkout, text=True
    ).strip()
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "source.tar"
        src = Path(temp) / "source"
        subprocess.run(
            ["git", "archive", "-o", str(archive), commit], cwd=checkout, check=True
        )
        with tarfile.open(archive) as bundle:
            bundle.extractall(src, filter="data")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--wheel-dir",
                str(directory),
                ".",
            ],
            cwd=src,
            env={**os.environ, "SOURCE_DATE_EPOCH": epoch},
            check=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wheel-dir", type=Path, help="Directory containing the verified wheel"
    )
    parser.add_argument(
        "--save-wheel", type=Path, help="Retain the verified wheel for other runners"
    )
    parser.add_argument(
        "--checkout", type=Path, default=ROOT / ".qualification/companion-ide"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".qualification/environment"
    )
    args = parser.parse_args()
    pair = json.loads((ROOT / "docs/v0.8/IDE_PAIR.json").read_text(encoding="utf-8"))
    expected = pair["ide_wheel"]
    filename = f"openbexi_ide-{pair['ide_version']}-py3-none-any.whl"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        wheel = directory / filename
        if args.wheel_dir:
            shutil.copyfile(args.wheel_dir / filename, wheel)
        elif expected.get("release_url"):
            with (
                urllib.request.urlopen(expected["release_url"], timeout=60) as src,
                wheel.open("wb") as dst,
            ):
                shutil.copyfileobj(src, dst)
        else:
            build_pinned_wheel(args.checkout, pair["ide_commit"], directory)
        with wheel.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != expected["sha256"]:
            raise ValueError(
                f"{filename} SHA-256 {digest} differs from {expected['sha256']}"
            )
        if args.save_wheel:
            args.save_wheel.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(wheel, args.save_wheel / filename)
        receipt = output / "paired-ide-install.json"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--force-reinstall",
                "--report",
                str(receipt),
                str(wheel),
            ],
            check=True,
        )
        installed = json.loads(receipt.read_text(encoding="utf-8"))["install"]
        if (
            len(installed) != 1
            or installed[0]["download_info"]["archive_info"]["hashes"]["sha256"]
            != digest
        ):
            raise ValueError("Pip installed a different artifact")
        print(f"Installed {filename} sha256={digest} companion={pair['ide_commit']}")


if __name__ == "__main__":
    main()
