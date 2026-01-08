#!/bin/bash
# Runs E2E tests in KIND cluster with local registry.
# This script builds all images, pushes them to the local registry, and runs tests.
set -o errexit

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Configuration
REG_PORT="${REGISTRY_PORT:-5001}"
LOCAL_REGISTRY="localhost:${REG_PORT}"

echo "=== Building and pushing images to local registry ==="

# Build and push operator
echo "Building operator image..."
docker build -t "${LOCAL_REGISTRY}/agentic-operator:latest" "${PROJECT_ROOT}/operator/"
docker push "${LOCAL_REGISTRY}/agentic-operator:latest"

# Build and push agent runtime
echo "Building agent runtime image..."
docker build -t "${LOCAL_REGISTRY}/agentic-agent:latest" "${PROJECT_ROOT}/python/"
docker push "${LOCAL_REGISTRY}/agentic-agent:latest"

# Tag same image for MCP server (they use the same base)
docker tag "${LOCAL_REGISTRY}/agentic-agent:latest" "${LOCAL_REGISTRY}/agentic-mcp-server:latest"
docker push "${LOCAL_REGISTRY}/agentic-mcp-server:latest"

# Pull and push external images to local registry
echo "Pulling and pushing LiteLLM image..."
docker pull ghcr.io/berriai/litellm:main-latest
docker tag ghcr.io/berriai/litellm:main-latest "${LOCAL_REGISTRY}/litellm:latest"
docker push "${LOCAL_REGISTRY}/litellm:latest"

echo "Pulling and pushing Ollama image..."
docker pull alpine/ollama:latest
docker tag alpine/ollama:latest "${LOCAL_REGISTRY}/ollama:latest"
docker push "${LOCAL_REGISTRY}/ollama:latest"

echo "=== Creating Helm values for KIND registry ==="
cat > /tmp/kind-e2e-values.yaml << EOF
controllerManager:
  manager:
    image:
      repository: ${LOCAL_REGISTRY}/agentic-operator
      tag: latest
    imagePullPolicy: Always
defaultImages:
  agentRuntime: ${LOCAL_REGISTRY}/agentic-agent:latest
  mcpServer: ${LOCAL_REGISTRY}/agentic-mcp-server:latest
  litellm: ${LOCAL_REGISTRY}/litellm:latest
  ollama: ${LOCAL_REGISTRY}/ollama:latest
EOF

echo "Helm values file:"
cat /tmp/kind-e2e-values.yaml

echo ""
echo "=== Running E2E tests ==="
cd "${PROJECT_ROOT}/operator/tests"

# Ensure virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
else
    source .venv/bin/activate
fi

# Pre-install operator with Gateway
echo "Pre-installing operator to get Gateway..."
kubectl create namespace agentic-e2e-system 2>/dev/null || true
kubectl apply --server-side -f "${PROJECT_ROOT}/operator/config/crd/bases"
helm upgrade --install agentic-e2e "${PROJECT_ROOT}/operator/chart" \
    --namespace agentic-e2e-system \
    -f /tmp/kind-e2e-values.yaml \
    --set gatewayAPI.enabled=true \
    --set gatewayAPI.createGateway=true \
    --set gatewayAPI.gatewayClassName=envoy-gateway \
    --skip-crds \
    --wait --timeout 120s

# Wait for Gateway to be programmed
echo "Waiting for Gateway to be programmed..."
for i in {1..30}; do
    STATUS=$(kubectl get gateway agentic-gateway -n agentic-e2e-system -o jsonpath='{.status.conditions[?(@.type=="Programmed")].status}' 2>/dev/null || echo "")
    if [ "$STATUS" = "True" ]; then
        echo "Gateway is programmed!"
        break
    fi
    echo "Waiting for Gateway... (attempt $i/30)"
    sleep 2
done

# Get the Envoy Gateway service for port-forwarding
GATEWAY_SVC=$(kubectl get svc -n envoy-gateway-system -l "gateway.envoyproxy.io/owning-gateway-name=agentic-gateway" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -z "$GATEWAY_SVC" ]; then
    echo "ERROR: Could not find Gateway service"
    kubectl get svc -n envoy-gateway-system
    exit 1
fi
echo "Found Gateway service: ${GATEWAY_SVC}"

# Start port-forward in background
echo "Starting port-forward to Gateway..."
kubectl port-forward -n envoy-gateway-system "svc/${GATEWAY_SVC}" 8888:80 &
PORT_FORWARD_PID=$!
sleep 3

# Verify port-forward is working
if ! curl -s --connect-timeout 5 http://localhost:8888 > /dev/null 2>&1; then
    echo "Warning: Port-forward may not be ready, waiting longer..."
    sleep 5
fi

# Cleanup function
cleanup() {
    echo "Stopping port-forward..."
    kill $PORT_FORWARD_PID 2>/dev/null || true
}
trap cleanup EXIT

# Run tests with Gateway URL set to localhost port-forward
# Note: We don't call 'make test' because it runs 'make clean' which deletes the Gateway
export HELM_VALUES_FILE=/tmp/kind-e2e-values.yaml
export GATEWAY_URL="http://localhost:8888"
echo "Using Gateway URL: ${GATEWAY_URL}"

# Clean up any leftover test namespaces (but not the operator namespace with Gateway!)
echo "Cleaning up leftover test namespaces..."
kubectl get ns -o name | grep -E "e2e-gw[0-9]+" | xargs -I{} kubectl delete {} --wait=false 2>/dev/null || true
sleep 2

# Run pytest directly (skip 'make test' which would clean the operator)
NPROC=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
python -m pytest e2e/ -v -n ${NPROC} --dist loadscope
