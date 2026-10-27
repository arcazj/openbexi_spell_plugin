"""Generate *prelaunch-only* Kubernetes objects without embedding credentials.

Each deployment requires a separately provisioned Kubernetes Secret with only
the role's ca.pem, tls.crt, tls.key and config.json, never a shared secret.
No worker Pods, runtime mutation routes, native launch, ingress or service token.
"""
import argparse
import json
from pathlib import Path

NAMESPACE = "openbexi-v08"
ROLES = {"context-a": 9441, "context-b": 9442, "listener": 9444, "gateway": 9443, "dss": 8085}
CONTEXTS = ("context-a", "context-b")
AUTHORITY_IMAGE = "openbexi-spell-server:0.8.0.dev71-prelaunch"
DSS_IMAGE = "openbexi-spell-plugin-dss:0.1.0"


def meta(name, labels=None):
    value = {"name": name, "namespace": NAMESPACE}
    if labels:
        value["labels"] = labels
    return value


def service_account():
    return {"apiVersion": "v1", "kind": "ServiceAccount",
            "metadata": meta("v08-no-k8s-api"),
            "automountServiceAccountToken": False}


def pvc(name):
    return {"apiVersion": "v1", "kind": "PersistentVolumeClaim",
            "metadata": meta(name),
            "spec": {"accessModes": ["ReadWriteOnce"],
                     "resources": {"requests": {"storage": "1Gi"}}}}


def deployment(role, port):
    is_dss = role == "dss"
    is_context = role in CONTEXTS
    uid = 10003 if is_dss else 65532
    image = DSS_IMAGE if is_dss else AUTHORITY_IMAGE
    container = {
        "name": role,
        "image": image,
        "imagePullPolicy": "IfNotPresent",
        "args": (
            ["--port", "8085", "--database", "/var/lib/dss/dss.sqlite"]
            if is_dss else [("context" if is_context else role), "--config", "/run/private/config.json"]
        ),
        "ports": [{"name": "https" if not is_dss else "http", "containerPort": port}],
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        },
        "resources": {
            "requests": {"cpu": "100m", "memory": "128Mi"},
            "limits": {"cpu": "500m", "memory": "512Mi" if not is_dss else "256Mi"},
        },
        "readinessProbe": (
            {"exec": {"command": ["python", "-I", "-c",
                "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8085/healthz',timeout=2).close()"]},
             "periodSeconds": 4, "timeoutSeconds": 3}
            if is_dss else
            {"tcpSocket": {"port": port}, "periodSeconds": 4, "timeoutSeconds": 3}
        ),
        "volumeMounts": (
            [{"name": "data", "mountPath": "/var/lib/dss"}]
            if is_dss else
            [{"name": "private", "mountPath": "/run/private", "readOnly": True}]
            + ([{"name": "data", "mountPath": "/state"}] if is_context else [])
        ),
    }
    volumes = (
        [{"name": "data", "persistentVolumeClaim": {"claimName": "v08-dss-state"}}]
        if is_dss else
        [{"name": "private", "secret": {
            "secretName": "v08-" + role + "-private", "defaultMode": 0o440,
            "items": [{"key": key, "path": key} for key in
                      ("ca.pem", "tls.crt", "tls.key", "config.json")]
        }}] + ([{"name": "data", "persistentVolumeClaim": {
            "claimName": "v08-" + role + "-state"}}] if is_context else [])
    )
    return {
        "apiVersion": "apps/v1", "kind": "Deployment",
        "metadata": meta(role, {"app": role, "openbexi-v08-scope": "prelaunch-only"}),
        "spec": {
            "replicas": 1,
            "strategy": {"type": "Recreate"},
            "selector": {"matchLabels": {"app": role}},
            "template": {
                "metadata": {"labels": {"app": role}},
                "spec": {
                    "serviceAccountName": "v08-no-k8s-api",
                    "automountServiceAccountToken": False,
                    "terminationGracePeriodSeconds": 30,
                    "securityContext": {
                        "runAsNonRoot": True, "runAsUser": uid, "runAsGroup": uid,
                        "fsGroup": uid, "fsGroupChangePolicy": "OnRootMismatch",
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [container],
                    "volumes": volumes,
                },
            },
        },
    }


def service(role, port):
    return {
        "apiVersion": "v1", "kind": "Service",
        "metadata": meta(role),
        "spec": {
            "type": "ClusterIP",
            "selector": {"app": role},
            "ports": [{
                "name": "https" if role != "dss" else "http",
                "port": port, "targetPort": port, "protocol": "TCP",
            }],
        },
    }


def selector(*names):
    return {"podSelector": {"matchExpressions": [{
        "key": "app", "operator": "In", "values": list(names),
    }]}}


def port_rule(*ports):
    return [{"protocol": "TCP", "port": p} for p in ports]


def netpol(name, selected, *, ingress=None, egress=None):
    spec = {"podSelector": selector(*selected)["podSelector"]}
    types = []
    if ingress is not None:
        types.append("Ingress")
        spec["ingress"] = ingress
    if egress is not None:
        types.append("Egress")
        spec["egress"] = egress
    spec["policyTypes"] = types
    return {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
            "metadata": meta(name), "spec": spec}


def resources():
    result = [{
        "apiVersion": "v1", "kind": "Namespace",
        "metadata": {"name": NAMESPACE,
                     "labels": {"openbexi-v08-scope": "prelaunch-only"}},
    }, service_account()]
    result += [pvc("v08-" + name + "-state") for name in (*CONTEXTS, "dss")]
    # Install the default deny *before* creating any workload, so even a
    # fast-starting Pod cannot open an unrestricted egress/ingress window.
    result.append({
        "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
        "metadata": meta("v08-default-deny"),
        "spec": {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]},
    })
    for name, port in ROLES.items():
        result.extend((deployment(name, port), service(name, port)))
    result.append(netpol("v08-dns-only", tuple(ROLES), egress=[{
        "to": [{"namespaceSelector": {"matchLabels": {
            "kubernetes.io/metadata.name": "kube-system"}},
            "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}}}],
        "ports": [{"protocol": p, "port": 53} for p in ("TCP", "UDP")],
    }]))
    result.extend((
        netpol("v08-gateway-to-listener", ("gateway",),
               egress=[{"to": [selector("listener")], "ports": port_rule(9444)}]),
        netpol("v08-listener-from-gateway", ("listener",),
               ingress=[{"from": [selector("gateway")], "ports": port_rule(9444)}]),
        netpol("v08-listener-to-contexts", ("listener",),
               egress=[{"to": [selector(*CONTEXTS)], "ports": port_rule(9441, 9442)}]),
        netpol("v08-contexts-from-listener", CONTEXTS,
               ingress=[{"from": [selector("listener")], "ports": port_rule(9441, 9442)}]),
        netpol("v08-contexts-to-dss", CONTEXTS,
               egress=[{"to": [selector("dss")], "ports": port_rule(8085)}]),
        netpol("v08-dss-from-contexts", ("dss",),
               ingress=[{"from": [selector(*CONTEXTS)], "ports": port_rule(8085)}]),
    ))
    return result


def validate(items):
    kinds = [o["kind"] for o in items]
    assert kinds.count("Namespace") == 1
    assert kinds.count("Deployment") == len(ROLES)
    assert kinds.count("Service") == len(ROLES)
    assert kinds.count("PersistentVolumeClaim") == 3
    assert kinds.count("NetworkPolicy") >= 7
    for o in items:
        if o["kind"] == "Namespace":
            assert o["metadata"]["name"] == NAMESPACE
        else:
            assert o["metadata"]["namespace"] == NAMESPACE
    deployments = {o["metadata"]["name"]: o for o in items if o["kind"] == "Deployment"}
    assert set(deployments) == set(ROLES)
    for role, resource in deployments.items():
        spec = resource["spec"]
        pod = spec["template"]["spec"]
        assert spec["replicas"] == 1 and spec["strategy"]["type"] == "Recreate"
        assert pod["automountServiceAccountToken"] is False
        assert pod["securityContext"]["runAsNonRoot"] is True
        assert pod["securityContext"]["runAsUser"] > 0
        assert pod["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
        assert not pod.get("hostNetwork") and not pod.get("hostPID")
        assert len(pod["containers"]) == 1
        image = pod["containers"][0]
        assert image["image"] in (AUTHORITY_IMAGE, DSS_IMAGE)
        assert "latest" not in image["image"]
        assert image["securityContext"] == {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        }
        assert not any(k in image for k in ("hostPort", "privileged"))
        if role != "dss":
            private = [v for v in pod["volumes"] if v["name"] == "private"]
            assert len(private) == 1
            assert private[0]["secret"]["secretName"] == "v08-" + role + "-private"
    assert all(o["spec"]["type"] == "ClusterIP" for o in items if o["kind"] == "Service")
    assert any(o["metadata"]["name"] == "v08-default-deny" and
               o["spec"]["policyTypes"] == ["Ingress", "Egress"] for o in items)
    first_deployment = next(i for i, obj in enumerate(items) if obj["kind"] == "Deployment")
    default_deny = next(i for i, obj in enumerate(items)
                        if obj["metadata"]["name"] == "v08-default-deny")
    assert default_deny < first_deployment
    assert not any(o["kind"] in ("Ingress", "RoleBinding", "ClusterRoleBinding",
                                 "DaemonSet", "Job") for o in items)
    return {"passed": True, "manifests": len(items), "namespace": NAMESPACE,
            "full_v08_qualified": False, "worker_execution_available": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    items = resources()
    result = validate(items)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"apiVersion": "v1", "kind": "List",
                                       "items": items}, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
