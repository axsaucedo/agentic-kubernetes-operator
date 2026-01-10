#!/bin/bash
# Based on: https://kind.sigs.k8s.io/docs/user/local-registry/
# Creates a KIND cluster with a local Docker registry for E2E testing.
set -o errexit

# Configuration
CLUSTER_NAME="${KIND_CLUSTER_NAME:-agentic-e2e}"
REG_NAME="${REGISTRY_NAME:-kind-registry}"
REG_PORT="${REGISTRY_PORT:-5001}"

echo "Creating KIND cluster '$CLUSTER_NAME' with local registry '$REG_NAME:$REG_PORT'..."

# 1. Create registry container unless it already exists
if [ "$(docker inspect -f '{{.State.Running}}' "${REG_NAME}" 2>/dev/null || true)" != 'true' ]; then
  echo "Starting local registry..."
  docker run \
    -d --restart=always -p "127.0.0.1:${REG_PORT}:5000" --network bridge --name "${REG_NAME}" \
    registry:2
else
  echo "Registry ${REG_NAME} already running"
fi

# 2. Create kind cluster with containerd registry config dir enabled
if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
  echo "Cluster ${CLUSTER_NAME} already exists"
else
  echo "Creating KIND cluster..."
  cat <<EOF | kind create cluster --name "${CLUSTER_NAME}" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry]
    config_path = "/etc/containerd/certs.d"
EOF
fi

# 3. Add the registry config to the nodes
REGISTRY_DIR="/etc/containerd/certs.d/localhost:${REG_PORT}"
for node in $(kind get nodes --name "${CLUSTER_NAME}"); do
  docker exec "${node}" mkdir -p "${REGISTRY_DIR}"
  cat <<EOF | docker exec -i "${node}" cp /dev/stdin "${REGISTRY_DIR}/hosts.toml"
[host."http://${REG_NAME}:5000"]
EOF
done

# 4. Connect the registry to the cluster network if not already connected
if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${REG_NAME}")" = 'null' ]; then
  docker network connect "kind" "${REG_NAME}"
fi

# 5. Document the local registry (KEP-1755)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REG_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

echo ""
echo "KIND cluster '${CLUSTER_NAME}' is ready!"
echo "Local registry: localhost:${REG_PORT}"
echo ""
echo "To use: docker build -t localhost:${REG_PORT}/myimage:tag . && docker push localhost:${REG_PORT}/myimage:tag"
