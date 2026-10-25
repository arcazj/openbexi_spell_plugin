# Kubernetes: isolated **prelaunch staging** profile

`render_kubernetes.py` produces a Kubernetes `List` that can be checked
and applied to a throwaway test namespace **openbexi-v08**. It is deliberately
**not** the production Kubernetes v0.8 topology; it contains no native
Executor Pods, no worker admission controller, no browser WSS, no public
Ingress and no cross-namespace credentials.

The generated deployment uses five distinct processes (Gateway, Listener,
Context A, Context B and DSS), independent Context PVCs and dedicated leaf
certificate Secrets per component. All services are ClusterIP. There are
no RBAC RoleBindings, no service-account token mounts, no privileged or
root containers, no host networks and no broad pod ingress/egress. Network
policy enforces gateway→Listener→Context, Context→DSS and qualified DNS
only. Deployments use Recreate strategy and the Context SQLite process
enforces its own exclusive file lock.

## Render and validate syntax

```bash
python3.13 deploy/v0.8/render_kubernetes.py --output /tmp/v08-prelaunch-resources.json
python3.13 -m json.tool /tmp/v08-prelaunch-resources.json >/dev/null
kubectl apply --dry-run=client -f /tmp/v08-prelaunch-resources.json
```

The optional kubectl command needs an appropriate local client and cluster
API discovery. **A rendered manifest is not a deployed or fault-tested
Kubernetes workload.**

## Inject fresh secrets (do not commit the output)

Use `provision.py` to create a one-use CA and **distinct role secrets**
outside Git. Apply the Namespace object first. Before applying Deployments,
create four Kubernetes Secrets, one per role:

```bash
export V08_DEPLOY_ROOT=/secure/one-use/v08-private
kubectl apply -f /tmp/v08-prelaunch-resources.json --dry-run=client
kubectl create namespace openbexi-v08
for role in gateway listener context-a context-b; do
  kubectl -n openbexi-v08 create secret generic "v08-${role}-private" \
    --from-file="ca.pem=$V08_DEPLOY_ROOT/$role/ca.pem" \
    --from-file="tls.crt=$V08_DEPLOY_ROOT/$role/tls.crt" \
    --from-file="tls.key=$V08_DEPLOY_ROOT/$role/tls.key" \
    --from-file="config.json=$V08_DEPLOY_ROOT/$role/config.json"
done
kubectl apply -f /tmp/v08-prelaunch-resources.json
```

Adapt image references to privately published, verified images and provide
storage classes with actual backup/recovery guarantees before execution.
The server image and synthetic DSS image referenced here are development
builds; no signed multi-arch releases have been qualified. In a disposable
kind cluster load both images into the kind nodes before deploying.

The Gateway has no public load balancer. A local operator can test with
`kubectl -n openbexi-v08 port-forward service/gateway 19443:9443` and
the existing `qualify_compose.py` TLS client, which verifies the pinned
gateway leaf and the full private routing chain. This is a **local
prelaunch simulation**, not production user authentication, recovery or
network partition qualification.

**Release state:** `kubernetes.qualified=false`,
`native_family.qualified=false` and `full_v08_qualified=false`. A
real cluster/Pod identity qualification, dynamic worker admission, Pod UID
fencing, node partition, storage restore/rollout/rollback, complete native
mutation/barrier/effect proof and independent security review remain mandatory.
