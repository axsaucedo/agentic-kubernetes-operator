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
docker pull ollama/ollama:latest
docker tag ollama/ollama:latest "${LOCAL_REGISTRY}/ollama:latest"
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

# Run tests
export HELM_VALUES_FILE=/tmp/kind-e2e-values.yaml
make test
