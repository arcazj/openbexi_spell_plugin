"""Create isolated, one-use mTLS credentials for the prelaunch Compose test.

Never store generated private keys, CA keys, or client credentials in Git.
Not a production CA, issuance, rotation, backup, revocation or secret store.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess

ROLES = ("context-a", "context-b", "listener", "gateway", "alice", "bob", "observer")
PERMISSIONS = [
    "context:read",
    "blackboard:read",
    "blackboard:admin",
    "execution:read",
    "execution:start",
    "execution:control",
    "execution:request_control",
]


def openssl(*args):
    subprocess.run(
        ("openssl", *map(str, args)), check=True,
        timeout=25, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def pin(path):
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(path.read_text())).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    path.chmod(0o600)


def provision(root):
    root = root.resolve()
    if root.exists():
        raise ValueError("Private target already exists; refusal prevents key/authority reuse")
    old_umask = os.umask(0o077)
    try:
        root.mkdir(parents=True, mode=0o700)
        ca = root / "issuer"
        ca.mkdir(mode=0o700)
        openssl(
            "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-days", "1", "-subj", "/CN=OpenBEXI-Qualification-Only-CA",
            "-addext", "basicConstraints=critical,CA:TRUE",
            "-addext", "keyUsage=critical,keyCertSign,cRLSign",
            "-keyout", ca / "ca.key", "-out", ca / "ca.pem",
        )
        fingerprints = {}
        for role in ROLES:
            directory = root / role
            directory.mkdir(mode=0o700)
            key = directory / "tls.key"
            cert = directory / "tls.crt"
            request = ca / (role + ".csr")
            ext = ca / (role + ".ext")
            # Each role has an independent private key, leaf fingerprint and mount.
            ext.write_text(
                f"subjectAltName=DNS:{role},DNS:localhost,IP:127.0.0.1\n"
                "basicConstraints=critical,CA:FALSE\n"
                "keyUsage=critical,digitalSignature,keyEncipherment\n"
                "extendedKeyUsage=serverAuth,clientAuth\n"
            )
            openssl(
                "req", "-newkey", "rsa:2048", "-nodes",
                "-subj", "/CN=" + role, "-keyout", key, "-out", request,
            )
            openssl(
                "x509", "-req", "-in", request, "-CA", ca / "ca.pem",
                "-CAkey", ca / "ca.key", "-CAcreateserial",
                "-days", "1", "-extfile", ext, "-out", cert,
            )
            shutil.copyfile(ca / "ca.pem", directory / "ca.pem")
            key.chmod(0o600)
            (directory / "ca.pem").chmod(0o600)
            cert.chmod(0o600)
            fingerprints[role] = pin(cert)
        common = {
            "ca": "/run/private/ca.pem",
            "certificate": "/run/private/tls.crt",
            "key": "/run/private/tls.key",
            "bind": "0.0.0.0",
            "max_handlers": 16,
        }
        actors = {
            "alice": PERMISSIONS,
            "bob": PERMISSIONS,
            "observer": ["context:read", "execution:read"],
        }
        for name, port, context_id in (("context-a", 9441, "A"), ("context-b", 9442, "B")):
            write(root / name / "config.json", {
                **common, "port": port, "allowed_hosts": [f"{name}:{port}"],
                "context_id": context_id, "state_directory": "/state",
                "listener_fingerprint": fingerprints["listener"], "subjects": actors,
                # Logical reservation slots only. NO native workers are launched.
                "worker_slots": {f"slot-{i}": f"{context_id}-worker-{i}" for i in range(2)},
            })
        write(root / "listener" / "config.json", {
            **common, "port": 9444, "allowed_hosts": ["listener:9444"],
            "edge_fingerprint": fingerprints["gateway"],
            "identities": {
                fingerprints[name]: name for name in ("alice", "bob", "observer")
            },
            "scopes": {"alice": ["A", "B"], "bob": ["B"], "observer": ["A"]},
            "contexts": {
                "A": {
                    "url": "https://context-a:9441",
                    "fingerprint": fingerprints["context-a"],
                },
                "B": {
                    "url": "https://context-b:9442",
                    "fingerprint": fingerprints["context-b"],
                },
            },
        })
        write(root / "gateway" / "config.json", {
            **common, "port": 9443, "allowed_hosts": ["127.0.0.1:19443"],
            "listener_url": "https://listener:9444",
            "listener_fingerprint": fingerprints["listener"],
            "clients": [fingerprints[n] for n in ("alice", "bob", "observer")],
        })
        for name in ("state-a", "state-b"):
            (root / name).mkdir(mode=0o700)
        write(root / "pins.json", {"gateway": fingerprints["gateway"]})
        return {"root": str(root), "roles": len(ROLES), "private": True}
    finally:
        os.umask(old_umask)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(provision(args.output)))


if __name__ == "__main__":
    main()
