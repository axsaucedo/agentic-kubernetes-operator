#!/bin/bash
# Deletes the KIND cluster and local registry.
set -o errexit

# Configuration
CLUSTER_NAME="${KIND_CLUSTER_NAME:-agentic-e2e}"
REG_NAME="${REGISTRY_NAME:-kind-registry}"

echo "Deleting KIND cluster '${CLUSTER_NAME}'..."
kind delete cluster --name "${CLUSTER_NAME}" 2>/dev/null || true

echo "Removing local registry '${REG_NAME}'..."
docker rm -f "${REG_NAME}" 2>/dev/null || true

echo "Cleanup complete!"
