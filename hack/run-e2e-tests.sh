#!/bin/bash
# Runs E2E tests in KIND cluster with local registry.
# This script builds all images, pushes them to the local registry, and runs tests.
set -o errexit

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Configuration
REG_PORT="${REGISTRY_PORT:-5001}"
LOCAL_REGISTRY="localhost:${REG_PORT}"

# Image versions (pinned for reproducibility)
OPERATOR_TAG="dev"
AGENT_TAG="dev"
LITELLM_VERSION="v1.56.5"
# alpine/ollama only has 'latest' tag - using it for simplicity
OLLAMA_TAG="latest"

echo "=== Building and pushing images to local registry ==="

# Build and push operator
echo "Building operator image..."
docker build -t "${LOCAL_REGISTRY}/agentic-operator:${OPERATOR_TAG}" "${PROJECT_ROOT}/operator/"
docker push "${LOCAL_REGISTRY}/agentic-operator:${OPERATOR_TAG}"

# Build and push agent runtime
echo "Building agent runtime image..."
docker build -t "${LOCAL_REGISTRY}/agentic-agent:${AGENT_TAG}" "${PROJECT_ROOT}/python/"
docker push "${LOCAL_REGISTRY}/agentic-agent:${AGENT_TAG}"

# Tag same image for MCP server (they use the same base)
docker tag "${LOCAL_REGISTRY}/agentic-agent:${AGENT_TAG}" "${LOCAL_REGISTRY}/agentic-mcp-server:${AGENT_TAG}"
docker push "${LOCAL_REGISTRY}/agentic-mcp-server:${AGENT_TAG}"

# Build minimal LiteLLM image from our Dockerfile
echo "Building minimal LiteLLM image..."
docker build -t "${LOCAL_REGISTRY}/litellm:${LITELLM_VERSION}" -f "${SCRIPT_DIR}/Dockerfile.litellm" "${SCRIPT_DIR}"
docker push "${LOCAL_REGISTRY}/litellm:${LITELLM_VERSION}"

# Pull and push Ollama image (using alpine/ollama for smaller size)
echo "Pulling and pushing Ollama image..."
docker pull "alpine/ollama:${OLLAMA_TAG}"
docker tag "alpine/ollama:${OLLAMA_TAG}" "${LOCAL_REGISTRY}/ollama:${OLLAMA_TAG}"
docker push "${LOCAL_REGISTRY}/ollama:${OLLAMA_TAG}"

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

# Use the checked-in values file
HELM_VALUES_FILE="${SCRIPT_DIR}/kind-e2e-values.yaml"
echo "Using Helm values: ${HELM_VALUES_FILE}"

# Pre-install operator with Gateway
echo "Pre-installing operator to get Gateway..."
kubectl create namespace agentic-e2e-system 2>/dev/null || true
kubectl apply --server-side -f "${PROJECT_ROOT}/operator/config/crd/bases"
helm upgrade --install agentic-e2e "${PROJECT_ROOT}/operator/chart" \
    --namespace agentic-e2e-system \
    -f "${HELM_VALUES_FILE}" \
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

# Run tests with Gateway URL and Helm values
export HELM_VALUES_FILE="${HELM_VALUES_FILE}"
export GATEWAY_URL="http://localhost:8888"
echo "Using Gateway URL: ${GATEWAY_URL}"

# Clean up any leftover test namespaces (but not the operator namespace with Gateway!)
echo "Cleaning up leftover test namespaces..."
kubectl get ns -o name | grep -E "e2e-gw[0-9]+" | xargs -I{} kubectl delete {} --wait=false 2>/dev/null || true
sleep 2

# Run tests using make test (clean target has been removed from test dependency)
make test
