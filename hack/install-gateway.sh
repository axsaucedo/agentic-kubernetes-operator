#!/bin/bash
# Installs Gateway API CRDs and Envoy Gateway controller for E2E testing.
set -o errexit

GATEWAY_API_VERSION="${GATEWAY_API_VERSION:-v1.3.0}"

echo "Installing Gateway API CRDs (${GATEWAY_API_VERSION})..."
kubectl apply -f "https://github.com/kubernetes-sigs/gateway-api/releases/download/${GATEWAY_API_VERSION}/experimental-install.yaml"

echo "Waiting for Gateway API CRDs..."
kubectl wait --for condition=established --timeout=60s crd/gateways.gateway.networking.k8s.io
kubectl wait --for condition=established --timeout=60s crd/httproutes.gateway.networking.k8s.io

echo "Installing Envoy Gateway..."
helm upgrade --install envoy-gateway oci://docker.io/envoyproxy/gateway-helm \
  --namespace envoy-gateway-system --create-namespace \
  --wait --timeout 120s

echo ""
echo "Gateway API and Envoy Gateway installed successfully!"
