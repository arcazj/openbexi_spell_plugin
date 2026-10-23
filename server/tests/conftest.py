import hashlib
import ssl
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbexi_spell_server.transport import tls_context  # noqa: E402


@pytest.fixture(scope="session")
def pki(tmp_path_factory):
    root = tmp_path_factory.mktemp("private-test-pki")

    def run(*args):
        subprocess.run(
            ["openssl", *map(str, args)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )

    run(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-days",
        "1",
        "-subj",
        "/CN=test-ca",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        "-keyout",
        root / "ca.key",
        "-out",
        root / "ca.pem",
    )
    result = {"ca": root / "ca.pem"}
    extension = root / "extensions.cnf"
    extension.write_text(
        "subjectAltName=DNS:localhost,IP:127.0.0.1\n"
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth,clientAuth\n"
    )
    for name in ("edge", "listener", "context-a", "context-b", "worker"):
        key, cert = root / (name + ".key"), root / (name + ".pem")
        run(
            "req",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-subj",
            "/CN=" + name,
            "-keyout",
            key,
            "-out",
            root / (name + ".csr"),
        )
        run(
            "x509",
            "-req",
            "-in",
            root / (name + ".csr"),
            "-CA",
            root / "ca.pem",
            "-CAkey",
            root / "ca.key",
            "-CAcreateserial",
            "-days",
            "1",
            "-extfile",
            extension,
            "-out",
            cert,
        )
        pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
        result[name] = dict(
            cert=cert,
            key=key,
            pin=pin,
            client=tls_context(root / "ca.pem", cert, key),
            server=tls_context(root / "ca.pem", cert, key, server=True),
        )
    return result


from openbexi_spell_server.snapshots import git_manifest  # noqa: E402


def git(root, *args):
    return (
        subprocess.check_output(
            ["git", "-C", str(root), *args], stderr=subprocess.DEVNULL, timeout=5
        )
        .decode()
        .strip()
    )


def commit(root, *, stage=True):
    if stage:
        git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Qualification",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "source",
    )
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def source(tmp_path):
    root, exported = tmp_path / "git", tmp_path / "snapshot"
    root.mkdir()
    git(root, "init", "-q")
    (root / "main.py").write_text("print('approved source; never executed in preflight')\n")
    (root / "lib").mkdir()
    (root / "lib/helper.py").write_text("VALUE = 42\n")
    revision = commit(root)
    manifest = git_manifest(root, revision, "main.py")
    exported.mkdir()
    for file in manifest["files"]:
        target = exported / file["path"]
        target.parent.mkdir(exist_ok=True)
        target.write_bytes((root / file["path"]).read_bytes())
        target.chmod(0o755 if file["mode"] == "100755" else 0o644)
    entry = dict(
        repository=str(root),
        revision=revision,
        entrypoint="main.py",
        runtime_image="sha256:" + "c" * 64,
        driver_binding="simulator",
        aliases=["alias"],
    )
    return dict(
        root=root,
        directory=exported,
        revision=revision,
        manifest=manifest,
        config={"procedure": entry},
    )
