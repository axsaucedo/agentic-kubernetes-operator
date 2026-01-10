#!/bin/bash
# Build and push images to a registry for KIND E2E tests.
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

# Find project root (works from hack/ or project root)
if [ -d "${SCRIPT_DIR}/../operator" ]; then
    PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
elif [ -d "${SCRIPT_DIR}/operator" ]; then
    PROJECT_ROOT="${SCRIPT_DIR}"
else
    echo "ERROR: Cannot find project root"
    exit 1
fi

echo "Building and pushing images to ${REGISTRY}..."
echo "  OPERATOR_TAG: ${OPERATOR_TAG}"
echo "  AGENT_TAG: ${AGENT_TAG}"
echo "  LITELLM_VERSION: ${LITELLM_VERSION}"
echo "  OLLAMA_TAG: ${OLLAMA_TAG}"
echo ""

# Build and push operator
echo "Building operator image..."
docker build -t "${REGISTRY}/agentic-operator:${OPERATOR_TAG}" "${PROJECT_ROOT}/operator/"
docker push "${REGISTRY}/agentic-operator:${OPERATOR_TAG}"

# Build and push agent runtime
echo "Building agent runtime image..."
docker build -t "${REGISTRY}/agentic-agent:${AGENT_TAG}" "${PROJECT_ROOT}/python/"
docker push "${REGISTRY}/agentic-agent:${AGENT_TAG}"

# Tag same image for MCP server (they use the same base)
docker tag "${REGISTRY}/agentic-agent:${AGENT_TAG}" "${REGISTRY}/agentic-mcp-server:${AGENT_TAG}"
docker push "${REGISTRY}/agentic-mcp-server:${AGENT_TAG}"

# Build minimal LiteLLM image from our Dockerfile
echo "Building minimal LiteLLM image..."
docker build -t "${REGISTRY}/litellm:${LITELLM_VERSION}" -f "${SCRIPT_DIR}/Dockerfile.litellm" "${SCRIPT_DIR}"
docker push "${REGISTRY}/litellm:${LITELLM_VERSION}"

# Pull and push Ollama image (using alpine/ollama for smaller size)
echo "Pulling and pushing Ollama image..."
docker pull "alpine/ollama:${OLLAMA_TAG}"
docker tag "alpine/ollama:${OLLAMA_TAG}" "${REGISTRY}/ollama:${OLLAMA_TAG}"
docker push "${REGISTRY}/ollama:${OLLAMA_TAG}"

echo ""
echo "All images built and pushed successfully!"
