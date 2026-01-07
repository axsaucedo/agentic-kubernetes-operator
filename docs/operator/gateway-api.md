# Gateway API Integration

The Agentic Kubernetes Operator supports the [Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/) for exposing Agent, ModelAPI, and MCPServer resources via a unified ingress point.

## Overview

When Gateway API is enabled, the operator automatically creates HTTPRoute resources for each managed resource, allowing external access through a central Gateway.

```
┌─────────────────────────────────────────────────────────────────┐
│                         External Client                          │
│                              │                                   │
│         http://gateway-host/{namespace}/{type}/{name}/...        │
└──────────────────────────────┼──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                          Gateway                                 │
│                    (envoy, nginx, etc.)                          │
│                              │                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ HTTPRoute   │  │ HTTPRoute   │  │ HTTPRoute   │              │
│  │ /ns/agent/a │  │/ns/modelapi/│  │ /ns/mcp/m   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        User Namespace                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Agent Service  │  │ ModelAPI Service│  │MCPServer Service│  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Gateway API CRDs** - Install the Gateway API CRDs:
   ```bash
   kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.3.0/experimental-install.yaml
   ```

2. **Gateway Controller** - Install a Gateway controller (e.g., Envoy Gateway, Kong, Nginx):
   ```bash
   # Example: Envoy Gateway
   helm install envoy-gateway oci://docker.io/envoyproxy/gateway-helm \
     --version v1.3.0 \
     --namespace envoy-gateway-system \
     --create-namespace
   ```

3. **GatewayClass** - Create a GatewayClass:
   ```bash
   kubectl apply -f - <<EOF
   apiVersion: gateway.networking.k8s.io/v1
   kind: GatewayClass
   metadata:
     name: envoy-gateway
   spec:
     controllerName: gateway.envoyproxy.io/gatewayclass-controller
   EOF
   ```

## Installation with Gateway API

### Using Helm

```bash
helm install agentic-operator ./operator/chart \
  --namespace agentic-system \
  --create-namespace \
  --set gatewayAPI.enabled=true \
  --set gatewayAPI.createGateway=true \
  --set gatewayAPI.gatewayClassName=envoy-gateway
```

### Helm Values

| Value | Default | Description |
|-------|---------|-------------|
| `gatewayAPI.enabled` | `false` | Enable Gateway API integration |
| `gatewayAPI.gatewayName` | `agentic-gateway` | Name of the Gateway resource |
| `gatewayAPI.gatewayNamespace` | Release namespace | Namespace of the Gateway |
| `gatewayAPI.createGateway` | `false` | Create a Gateway resource |
| `gatewayAPI.gatewayClassName` | Required if createGateway | GatewayClass to use |
| `gatewayAPI.listenerPort` | `80` | Port for HTTP listener |

### Using Existing Gateway

To use an existing Gateway instead of creating one:

```bash
helm install agentic-operator ./operator/chart \
  --namespace agentic-system \
  --create-namespace \
  --set gatewayAPI.enabled=true \
  --set gatewayAPI.gatewayName=my-gateway \
  --set gatewayAPI.gatewayNamespace=gateway-ns
```

## URL Structure

HTTPRoutes use a consistent path structure:

```
/{namespace}/{resource-type}/{resource-name}/...
```

| Resource Type | Path Pattern | Example |
|--------------|--------------|---------|
| Agent | `/{ns}/agent/{name}` | `/prod/agent/coordinator/health` |
| ModelAPI | `/{ns}/modelapi/{name}` | `/prod/modelapi/ollama-proxy/v1/chat/completions` |
| MCPServer | `/{ns}/mcp/{name}` | `/dev/mcp/echo-server/health` |

### Path Rewriting

The operator configures HTTPRoutes with URL rewriting to strip the path prefix. When you call:

```
http://gateway/my-namespace/agent/my-agent/health
```

The backend service receives:

```
/health
```

## Example: Accessing an Agent via Gateway

1. Deploy an agent:
   ```yaml
   apiVersion: ethical.institute/v1alpha1
   kind: Agent
   metadata:
     name: my-agent
     namespace: my-namespace
   spec:
     modelAPI: my-model
     config:
       description: "Example agent"
   ```

2. Access via Gateway:
   ```bash
   # Health check
   curl http://localhost/my-namespace/agent/my-agent/health
   
   # Agent card
   curl http://localhost/my-namespace/agent/my-agent/.well-known/agent
   
   # Chat completions
   curl http://localhost/my-namespace/agent/my-agent/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"my-agent","messages":[{"role":"user","content":"Hello"}]}'
   ```

## Verifying HTTPRoutes

Check created HTTPRoutes:

```bash
kubectl get httproutes -A
```

Example output:
```
NAMESPACE      NAME                     HOSTNAMES   AGE
my-namespace   agent-my-agent                       5m
my-namespace   modelapi-my-model                    5m
```

View HTTPRoute details:
```bash
kubectl get httproute agent-my-agent -n my-namespace -o yaml
```

## Disabling Gateway API

To run without Gateway API (using direct service access):

```bash
helm install agentic-operator ./operator/chart \
  --namespace agentic-system \
  --create-namespace
  # gatewayAPI.enabled defaults to false
```

Without Gateway API, access services via port-forward:
```bash
kubectl port-forward svc/agent-my-agent 8080:8000 -n my-namespace
curl http://localhost:8080/health
```

## Troubleshooting

### HTTPRoute Not Created

Check operator logs:
```bash
kubectl logs -n agentic-system deployment/agentic-operator-controller-manager | grep HTTPRoute
```

Verify Gateway API is enabled:
```bash
kubectl get configmap -n agentic-system agentic-operator-gateway-config -o yaml
```

### 404 Errors

1. Verify the HTTPRoute exists and is accepted:
   ```bash
   kubectl get httproute -n your-namespace -o wide
   ```

2. Check HTTPRoute status:
   ```bash
   kubectl describe httproute agent-your-agent -n your-namespace
   ```

3. Verify the Gateway is programmed:
   ```bash
   kubectl get gateway -n agentic-system
   ```

### RBAC Errors

If you see "forbidden" errors for httproutes, ensure the operator has proper RBAC:
```bash
kubectl get clusterrole agentic-operator-agentic-operator -o yaml | grep -A10 gateway
```

## Internal Routing (Future)

When Gateway API is enabled, agents can optionally use Gateway URLs for inter-agent communication instead of direct service DNS. This feature is planned for future releases.
