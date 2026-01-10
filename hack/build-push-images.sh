#!/bin/bash
# Build images and load into KIND cluster for E2E tests.
# This script is used by both run-e2e-tests.sh and GitHub Actions.
#
# Required environment variables:
#   REGISTRY - Image prefix (e.g., kind-local)
#   KIND_CLUSTER_NAME - KIND cluster name (default: agentic-e2e)
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
KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-agentic-e2e}"
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

echo "Building images..."
echo "  REGISTRY: ${REGISTRY}"
echo "  KIND_CLUSTER_NAME: ${KIND_CLUSTER_NAME}"
echo "  OPERATOR_TAG: ${OPERATOR_TAG}"
echo "  AGENT_TAG: ${AGENT_TAG}"
echo "  LITELLM_VERSION: ${LITELLM_VERSION}"
echo "  OLLAMA_TAG: ${OLLAMA_TAG}"
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

# Load images into KIND cluster
echo ""
echo "Loading images into KIND cluster '${KIND_CLUSTER_NAME}'..."
kind load docker-image "${REGISTRY}/agentic-operator:${OPERATOR_TAG}" --name "${KIND_CLUSTER_NAME}"
kind load docker-image "${REGISTRY}/agentic-agent:${AGENT_TAG}" --name "${KIND_CLUSTER_NAME}"
kind load docker-image "${REGISTRY}/agentic-mcp-server:${AGENT_TAG}" --name "${KIND_CLUSTER_NAME}"
kind load docker-image "${REGISTRY}/litellm:${LITELLM_VERSION}" --name "${KIND_CLUSTER_NAME}"
kind load docker-image "${REGISTRY}/ollama:${OLLAMA_TAG}" --name "${KIND_CLUSTER_NAME}"

echo ""
echo "All images built and loaded into KIND!"
