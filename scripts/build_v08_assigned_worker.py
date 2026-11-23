"""Build one Linux assigned-worker image from an exact native image and release wheels."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from build_v08_native_profile import ROOT, local_base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-image", required=True)
    parser.add_argument("--wheel-directory", type=Path, required=True)
    parser.add_argument("--server-sha256", required=True)
    parser.add_argument("--dss-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    base, base_id = local_base(args.native_image)
    hashes = {}
    with tempfile.TemporaryDirectory(prefix="openbexi-assigned-worker-") as temporary:
        build = Path(temporary)
        for role, checksum in (
            ("server", args.server_sha256),
            ("dss", args.dss_sha256),
        ):
            filename = f"openbexi_spell_{role}-0.8.0-py3-none-any.whl"
            shutil.copyfile(args.wheel_directory / filename, build / filename)
            hashes[filename] = hashlib.sha256(
                (build / filename).read_bytes()
            ).hexdigest()
            if hashes[filename] != checksum:
                raise ValueError(f"{role} wheel checksum differs")
        modules = build / "modules"
        modules.mkdir()
        for source, installed in (
            ("v08_worker", "agent"),
            ("native", "native_candidate"),
            ("children", "children"),
            ("child_gate", "child_gate"),
            ("control_journal", "control_journal"),
            ("prompt_replies", "prompt_replies"),
            ("handoff_runtime", "handoff_runtime"),
            ("epoch_relay", "epoch_relay"),
            ("startup_diagnostics", "startup_diagnostics"),
        ):
            target = modules / (installed + ".py")
            shutil.copyfile(ROOT / "host_runtime" / "python" / (source + ".py"), target)
            hashes["modules/" + target.name] = hashlib.sha256(
                target.read_bytes()
            ).hexdigest()
        (build / "Dockerfile").write_text(
            f"FROM {base}\n"
            "USER root\n"
            "COPY *.whl /wheels/\n"
            "RUN python -m pip install --no-compile --force-reinstall --no-deps --no-index /wheels/*.whl\n"
            "COPY modules/ /v08/\n"
            "USER 10003:10003\n"
            'ENTRYPOINT ["python","-I","/v08/agent.py","--config","/credentials/config.json"]\n'
        )
        iid = build / "image.id"
        subprocess.run(
            [
                "docker",
                "build",
                "--pull=false",
                "--network",
                "none",
                "--iidfile",
                str(iid),
                str(build),
            ],
            check=True,
        )
        image = iid.read_text().strip()
    receipt = dict(native_base=base_id, worker_image=image, inputs_sha256=hashes)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
    print(image)


if __name__ == "__main__":
    main()
