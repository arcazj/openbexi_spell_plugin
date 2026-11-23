"""Render one digest-pinned, single-use Kubernetes Job for an assigned native worker."""

import argparse
import json
from pathlib import Path
import re


WORKER_UID = 10003
SOURCE_INIT = """
import hashlib, os, sys, tarfile
from pathlib import Path
out = Path('/prepared')
(out / 'work').mkdir(mode=0o700)
if Path('/durable').exists():
    audit = Path('/durable/records')
    audit.mkdir(mode=0o700, exist_ok=True)
    audit.chmod(0o700)
    assert audit.stat().st_uid == os.getuid() and audit.stat().st_mode & 0o077 == 0
if len(sys.argv) > 1:
    archive = Path('/input/source.tar.gz')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == sys.argv[1]
    source = out / 'source'
    source.mkdir(mode=0o750)
    with tarfile.open(archive) as files:
        for entry in files:
            path = source / entry.name
            assert path.resolve().is_relative_to(source) and entry.isfile()
            path.parent.mkdir(exist_ok=True, parents=True)
            with path.open('xb') as target:
                target.write(files.extractfile(entry).read())
            path.chmod(entry.mode & 0o755)
"""


def worker_job(namespace, slot, worker_image, init_image, source_sha256, node=None):
    for name in (namespace, slot):
        if len(name) > 56 or not re.fullmatch(r"[a-z0-9](?:[-a-z0-9]*[a-z0-9])?", name):
            raise ValueError("Invalid Kubernetes namespace or worker slot")
    for image in (worker_image, init_image):
        if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", image):
            raise ValueError("Supply an OCI image reference by manifest digest")
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("Supply the SHA-256 of the approved source archive")
    secure = {
        "readOnlyRootFilesystem": True,
        "allowPrivilegeEscalation": False,
        "capabilities": {"drop": ["ALL"]},
    }
    init = {
        "name": "source", "image": init_image, "imagePullPolicy": "Never",
        "command": ["python", "-I", "-c", SOURCE_INIT, source_sha256],
        "securityContext": secure,
        "volumeMounts": [
            {"name": "input", "mountPath": "/input", "readOnly": True},
            {"name": "prepared", "mountPath": "/prepared", "readOnly": False},
            {"name": "persistent", "mountPath": "/durable", "readOnly": False},
        ],
        "resources": {"requests": {"cpu": "40m", "memory": "32Mi"}, "limits": {"cpu": "300m", "memory": "128Mi"}},
    }
    worker = {
        "name": "worker", "image": worker_image, "imagePullPolicy": "Never", "securityContext": secure,
        "env": [{"name": "OPENBEXI_V08_AUDIT_ROOT", "value": "/audit"}],
        "volumeMounts": [
            {"name": "creds", "mountPath": "/credentials", "readOnly": True},
            {"name": "tmp", "mountPath": "/tmp", "readOnly": False},
            {"name": "prepared", "mountPath": "/source", "subPath": "source", "readOnly": True},
            {"name": "persistent", "mountPath": "/audit", "subPath": "records", "readOnly": False},
            {"name": "prepared", "mountPath": "/workspace", "subPath": "work", "readOnly": False},
        ],
        "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "2", "memory": "1536Mi"}},
    }
    pod = {
        "restartPolicy": "Never", "terminationGracePeriodSeconds": 8,
        "serviceAccountName": "no-api", "automountServiceAccountToken": False, "enableServiceLinks": False,
        "securityContext": {"runAsNonRoot": True, "runAsUser": WORKER_UID, "runAsGroup": WORKER_UID,
                            "fsGroup": WORKER_UID, "fsGroupChangePolicy": "OnRootMismatch", "seccompProfile": {"type": "RuntimeDefault"}},
        "initContainers": [init], "containers": [worker],
        "volumes": [
            {"name": "creds", "secret": {"secretName": "identity-" + slot, "defaultMode": 0o440}},
            {"name": "tmp", "emptyDir": {"medium": "Memory", "sizeLimit": "128Mi"}},
            {"name": "input", "configMap": {"name": "source-snapshot"}},
            {"name": "prepared", "emptyDir": {"sizeLimit": "32Mi"}},
            {"name": "persistent", "persistentVolumeClaim": {"claimName": "audit-" + slot}},
        ],
    }
    if node:
        pod["nodeSelector"] = {"kubernetes.io/hostname": node}
    return {
        "apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": slot, "namespace": namespace},
        "spec": {"backoffLimit": 0, "template": {
            "metadata": {"labels": {"app": slot, "role": "worker", "openbexi-native": "qualification"}},
            "spec": pod,
        }},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("namespace", "slot", "worker-image", "init-image", "source-sha256"):
        parser.add_argument("--" + arg, required=True)
    parser.add_argument("--node", help="Optional preselected storage node")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = worker_job(args.namespace, args.slot, args.worker_image, args.init_image, args.source_sha256, args.node)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
