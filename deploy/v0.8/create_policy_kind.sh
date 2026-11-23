#!/usr/bin/env bash
set -euo pipefail
kind_cli=$1
work=$(mktemp -d)
cat > "$work/cluster.yaml" <<'YAML'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true
  podSubnet: 192.168.0.0/16
nodes:
  - role: control-plane
  - role: worker
  - role: worker
YAML
node='kindest/node:v1.32.2@sha256:f226345927d7e348497136874b6d207e0b32cc52154ad8323129352923a3142f'
"$kind_cli" create cluster --name v08prelaunch --image "$node" --config "$work/cluster.yaml"
base='https://raw.githubusercontent.com/projectcalico/calico/3302e8bfd48e6375013d1d79ccb2c693306400a9/manifests'
cd "$work"
for manifest in operator-crds tigera-operator custom-resources; do
    curl --fail --silent --show-error --retry 2 "$base/$manifest.yaml" -o "$manifest.yaml"
done
sha256sum --check <<'SUMS'
fde094dbdfab65687542c8fbde1fd4168bb52657166ea84af75b22544dff1d2e  operator-crds.yaml
06d2fec21cb7946c71e910086449e5a1e431e3898cf21e8c874c83ee864956b8  tigera-operator.yaml
f7cd142773609fc7f830b96d8f29bd1b5f05cdc5293324992d8524b54c09c717  custom-resources.yaml
SUMS
kubectl create -f operator-crds.yaml
kubectl wait --for=condition=Established crd/installations.operator.tigera.io --timeout=120s
kubectl create -f tigera-operator.yaml
kubectl create -f custom-resources.yaml
kubectl wait --for=create tigerastatus/calico --timeout=300s
kubectl wait --for=condition=Available tigerastatus/calico --timeout=420s
kubectl wait --for=condition=Ready nodes --all --timeout=150s
kubectl -n kube-system rollout status deployment/coredns --timeout=150s
