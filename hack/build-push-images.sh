#!/bin/bash
# Build images for KIND E2E tests.
# This script is used by both run-e2e-tests.sh and GitHub Actions.
#
# Required environment variables:
#   REGISTRY - Docker registry URL (e.g., localhost:5001)
#
# Optional environment variables (with defaults):
#   OPERATOR_TAG - Tag for operator image (default: dev)
#   AGENT_TAG - Tag for agent image (default: dev)
#   LITELLM_VERSION - LiteLLM version (default: v1.56.5)
#   OLLAMA_TAG - Ollama tag (default: latest)
#   KIND_CLUSTER_NAME - KIND cluster name for loading images (default: agentic-e2e)
#   USE_KIND_LOAD - If set to "true", use kind load instead of registry push
set -o errexit

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Validate required variables
if [ -z "${REGISTRY}" ]; then
    echo "ERROR: REGISTRY environment variable is required"
    exit 1
fi

# Set defaults
OPERATOR_TAG="${OPERATOR_TAG:-dev}"
AGENT_TAG="${AGENT_TAG:-dev}"
LITELLM_VERSION="${LITELLM_VERSION:-v1.56.5}"
OLLAMA_TAG="${OLLAMA_TAG:-latest}"
KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-agentic-e2e}"
USE_KIND_LOAD="${USE_KIND_LOAD:-false}"

# Find project root (works from hack/ or project root)
if [ -d "${SCRIPT_DIR}/../operator" ]; then
    PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
elif [ -d "${SCRIPT_DIR}/operator" ]; then
    PROJECT_ROOT="${SCRIPT_DIR}"
else
    echo "ERROR: Cannot find project root"
    exit 1
fi

echo "Building images..."
echo "  REGISTRY: ${REGISTRY}"
echo "  OPERATOR_TAG: ${OPERATOR_TAG}"
echo "  AGENT_TAG: ${AGENT_TAG}"
echo "  LITELLM_VERSION: ${LITELLM_VERSION}"
echo "  OLLAMA_TAG: ${OLLAMA_TAG}"
echo "  USE_KIND_LOAD: ${USE_KIND_LOAD}"
echo ""

# Build operator
echo "Building operator image..."
docker build -t "${REGISTRY}/agentic-operator:${OPERATOR_TAG}" "${PROJECT_ROOT}/operator/"

# Build agent runtime
echo "Building agent runtime image..."
docker build -t "${REGISTRY}/agentic-agent:${AGENT_TAG}" "${PROJECT_ROOT}/python/"

# Tag same image for MCP server (they use the same base)
docker tag "${REGISTRY}/agentic-agent:${AGENT_TAG}" "${REGISTRY}/agentic-mcp-server:${AGENT_TAG}"

# Build minimal LiteLLM image from our Dockerfile
echo "Building minimal LiteLLM image..."
docker build -t "${REGISTRY}/litellm:${LITELLM_VERSION}" -f "${SCRIPT_DIR}/Dockerfile.litellm" "${SCRIPT_DIR}"

# Pull and tag Ollama image (using alpine/ollama for smaller size)
echo "Pulling and tagging Ollama image..."
docker pull "alpine/ollama:${OLLAMA_TAG}"
docker tag "alpine/ollama:${OLLAMA_TAG}" "${REGISTRY}/ollama:${OLLAMA_TAG}"

# Either push to registry or load directly into KIND
if [ "${USE_KIND_LOAD}" = "true" ]; then
    echo ""
    echo "Loading images into KIND cluster '${KIND_CLUSTER_NAME}'..."
    kind load docker-image "${REGISTRY}/agentic-operator:${OPERATOR_TAG}" --name "${KIND_CLUSTER_NAME}"
    kind load docker-image "${REGISTRY}/agentic-agent:${AGENT_TAG}" --name "${KIND_CLUSTER_NAME}"
    kind load docker-image "${REGISTRY}/agentic-mcp-server:${AGENT_TAG}" --name "${KIND_CLUSTER_NAME}"
    kind load docker-image "${REGISTRY}/litellm:${LITELLM_VERSION}" --name "${KIND_CLUSTER_NAME}"
    kind load docker-image "${REGISTRY}/ollama:${OLLAMA_TAG}" --name "${KIND_CLUSTER_NAME}"
else
    echo ""
    echo "Pushing images to registry..."
    docker push "${REGISTRY}/agentic-operator:${OPERATOR_TAG}"
    docker push "${REGISTRY}/agentic-agent:${AGENT_TAG}"
    docker push "${REGISTRY}/agentic-mcp-server:${AGENT_TAG}"
    docker push "${REGISTRY}/litellm:${LITELLM_VERSION}"
    docker push "${REGISTRY}/ollama:${OLLAMA_TAG}"
fi

echo ""
echo "All images built successfully!"
