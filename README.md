# KAOS: K8s Agent Orchestration System

<p align="center">
  <img src="docs/assets/kaos-logo.svg" alt="KAOS Logo" width="200"/>
</p>

<p align="center">
  <strong>Deploy, manage, and orchestrate AI agents on Kubernetes</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#documentation">Documentation</a>
</p>

---

KAOS is a Kubernetes-native framework for deploying and orchestrating AI agents with tool access, multi-agent coordination, and seamless LLM integration.

## Features

- **🤖 Agent CRD** - Deploy AI agents as Kubernetes resources with declarative configuration
- **🔧 MCP Tools** - Integrate tools using the Model Context Protocol standard
- **🔗 Multi-Agent Networks** - Build hierarchical agent systems with automatic delegation
- **🌐 Gateway Integration** - Expose agents via Kubernetes Gateway API with automatic routing
- **📡 OpenAI-Compatible API** - All agents expose `/v1/chat/completions` endpoints
- **🔄 Agentic Loop** - Built-in reasoning loop with tool calling and agent delegation

## Quick Start

### Prerequisites

- Kubernetes cluster (Docker Desktop, kind, minikube)
- kubectl configured
- Helm 3.x
- (Optional) Ollama for local LLM inference

### Install KAOS Operator

```bash
# Add the KAOS Helm repository
helm repo add kaos https://axsaucedo.github.io/kaos

# Install the operator
helm install kaos-operator kaos/kaos-operator -n kaos-system --create-namespace
```

### Deploy Your First Agent

```yaml
# my-agent.yaml
apiVersion: kaos.dev/v1alpha1
kind: ModelAPI
metadata:
  name: ollama
spec:
  mode: Proxy
  proxyConfig:
    apiBase: "http://host.docker.internal:11434"

---
apiVersion: kaos.dev/v1alpha1
kind: MCPServer
metadata:
  name: echo-tools
spec:
  type: python-runtime
  config:
    mcp: "test-mcp-echo-server"

---
apiVersion: kaos.dev/v1alpha1
kind: Agent
metadata:
  name: assistant
spec:
  modelAPI: ollama
  mcpServers:
    - echo-tools
  config:
    description: "Helpful AI assistant with echo tools"
    instructions: "You are a helpful assistant. Use the echo tool when asked to repeat something."
    env:
      - name: MODEL_NAME
        value: "ollama/llama3.2:latest"
```

```bash
kubectl apply -f my-agent.yaml

# Port-forward to the agent
kubectl port-forward svc/assistant 8000:80

# Chat with your agent
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "assistant", "messages": [{"role": "user", "content": "Hello!"}]}'
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     KAOS Operator                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Agent     │  │  MCPServer  │  │  ModelAPI   │              │
│  │ Controller  │  │ Controller  │  │ Controller  │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   Agent Pod     │ │  MCP Server Pod │ │  LiteLLM Proxy  │
│  ┌───────────┐  │ │  ┌───────────┐  │ │  ┌───────────┐  │
│  │  Agent    │  │ │  │ MCP Tools │  │ │  │  LiteLLM  │──┼──► LLM Backend
│  │  Runtime  │──┼─┼─►│  Server   │  │ │  │   Proxy   │  │   (Ollama/OpenAI)
│  └───────────┘  │ │  └───────────┘  │ │  └───────────┘  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Components

| Component | Description |
|-----------|-------------|
| **Agent** | AI agent with LLM access, MCP tools, and delegation capabilities |
| **MCPServer** | Tool server implementing Model Context Protocol |
| **ModelAPI** | LiteLLM proxy for LLM backend abstraction |

## Multi-Agent Orchestration

KAOS supports building complex multi-agent systems with automatic delegation:

```yaml
apiVersion: kaos.dev/v1alpha1
kind: Agent
metadata:
  name: coordinator
spec:
  modelAPI: ollama
  config:
    description: "Coordinator that delegates to specialists"
    instructions: "Delegate research tasks to researcher, analysis to analyst."
  agentNetwork:
    access:
      - researcher
      - analyst

---
apiVersion: kaos.dev/v1alpha1
kind: Agent
metadata:
  name: researcher
spec:
  modelAPI: ollama
  mcpServers:
    - search-tools
  config:
    description: "Research specialist with search capabilities"

---
apiVersion: kaos.dev/v1alpha1
kind: Agent
metadata:
  name: analyst
spec:
  modelAPI: ollama
  mcpServers:
    - calculator-tools
  config:
    description: "Data analyst with calculation tools"
```

## Documentation

📚 **[Full Documentation](https://axsaucedo.github.io/kaos)**

- [Getting Started Guide](https://axsaucedo.github.io/kaos/getting-started/)
- [Agent CRD Reference](https://axsaucedo.github.io/kaos/operator/agent-crd/)
- [Multi-Agent Tutorial](https://axsaucedo.github.io/kaos/tutorials/multi-agent/)
- [Custom MCP Tools](https://axsaucedo.github.io/kaos/tutorials/custom-mcp-tools/)

## Development

### Run Tests

```bash
# Python unit tests
cd python && uv sync && uv run pytest tests/ -v

# Go unit tests
cd operator && make test

# E2E tests (requires kind)
cd operator && make kind-e2e
```

### Local Development

```bash
# Install CRDs
cd operator && make install

# Run operator locally
cd operator && make run

# Build agent image
cd python && docker build -t kaos-agent:latest .
```

## Sample Configurations

See [`operator/config/samples/`](operator/config/samples/) for example configurations:

1. **Simple Agent** - Single agent with echo MCP tool
2. **Multi-Agent** - Coordinator with worker agents
3. **Hierarchical** - Multi-level agent hierarchy
4. **Development** - Proxy to host Ollama for local dev

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.
