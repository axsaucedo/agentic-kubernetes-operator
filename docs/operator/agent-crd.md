# Agent CRD

The Agent custom resource defines an AI agent deployment on Kubernetes.

## Full Specification

```yaml
apiVersion: ethical.institute/v1alpha1
kind: Agent
metadata:
  name: my-agent
  namespace: my-namespace
spec:
  # Required: Reference to ModelAPI for LLM access
  modelAPI: my-modelapi
  
  # Optional: List of MCPServer references for tool access
  mcpServers:
  - echo-tools
  - calculator-tools
  
  # Optional: Agent configuration
  config:
    # Human-readable description for humans and other agents for a2a delegation
    description: "My helpful agent that performs tasks X/Y"
    
    # System prompt instructions
    instructions: |
      You are a helpful assistant.
      Be concise and accurate.
    
    # Agentic loop configuration
    # TODO: rename to just have reasoningLoopMaxSteps: as we don't need the rest
    # TODO: Remove the enableTools and the enableDelegation as this is redundant, also in the python code we should remove as both are just dictionaries so the cost of checking if there are no tools is minimal and just avoid requiring any env vars would reduce complexity
    agenticLoop:
      maxSteps: 5          # Max reasoning iterations (1-20)
      enableTools: true    # Enable tool calling
      enableDelegation: true  # Enable agent delegation
    
    # Additional environment variables
    env:
    - name: MODEL_NAME
      value: "smollm2:135m"
    - name: CUSTOM_VAR
      value: "custom-value"
  
  # Optional: Agent-to-Agent networking
  agentNetwork:
    # TODO: ENsure that expose is true by default
    # Create Service for A2A discovery (default true)
    #     this exposes an agent card at the ./well-known path
    expose: true           
    access:                # Sub-agents this agent can delegate to
    - worker-1
    - worker-2
  
  # TODO: Remove this replicas as we have this avaialbel in the podspec
  # Optional: Replica count
  replicas: 1
  
  # Advanced: We also provide a podSpec override section
  #   this allows you for custom overrides like images, etc
  # TODO: Add podspec override to allow for people to add overrides (eg image override, volume mounts, etc) - should use merge strategy, and this overides take prescedence
  podSpec:
    containers:
    # TODO: resources should be for podspec level
    - name: agent
      image: <your-custom-image>
      # Resource requirements
      resources:
        requests:
          memory: "256Mi"
          cpu: "200m"
        limits:
          memory: "512Mi"
          cpu: "1000m"

status:
  phase: Ready             # Pending, Ready, Failed, Waiting
  ready: true
  observedReplicas: 1
  endpoint: "http://my-agent.my-namespace.svc.cluster.local"
  linkedResources:
    modelAPI: my-modelapi
    mcpServers: "echo-tools,calculator-tools"
  message: ""
```

## Spec Fields

### modelAPI (required)

Reference to a ModelAPI resource in the same namespace.

```yaml
spec:
  modelAPI: my-modelapi
```

The agent waits for the ModelAPI to become Ready before starting (see `waitForDependencies`).

### mcpServers (optional)

List of MCPServer resource names in the same namespace.

```yaml
spec:
  mcpServers:
  - echo-tools
  - calculator-tools
```

All referenced MCPServers must be Ready for the agent to start (see `waitForDependencies`).

### waitForDependencies (optional)

Controls whether the agent waits for ModelAPI and MCPServers to be ready before creating the deployment.

```yaml
spec:
  waitForDependencies: true  # Default: true
```

| Value | Behavior |
|-------|----------|
| `true` (default) | Agent deployment is created only after ModelAPI and all MCPServers are Ready |
| `false` | Agent deployment is created immediately; agent handles unavailable dependencies gracefully at runtime |

Setting to `false` is useful when:
- Deploying agents in any order without worrying about startup sequence
- Using the Python agent's graceful degradation for unavailable sub-agents/tools

### config (optional)

Agent-specific configuration.

#### config.description

Human-readable description shown in agent card:

```yaml
config:
  description: "A research assistant agent"
```

#### config.instructions

System prompt for the agent:

```yaml
config:
  instructions: |
    You are a research assistant.
    When asked to research a topic:
    1. Search for relevant information
    2. Summarize findings concisely
    3. Cite your sources
```

# TODO: As outlied above to update as outlined above
#### config.agenticLoop

Configuration for the reasoning loop:

```yaml
config:
  agenticLoop:
    maxSteps: 10           # Allow more iterations for complex tasks
    enableTools: true      # Agent can call MCP tools
    enableDelegation: true # Agent can delegate to sub-agents
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `maxSteps` | int | 5 | Max reasoning iterations (1-20) |
| `enableTools` | bool | true | Enable tool calling |
| `enableDelegation` | bool | true | Enable agent delegation |

#### config.env

Additional environment variables:

```yaml
config:
  env:
  - name: MODEL_NAME
    value: "gpt-4"
  - name: API_KEY
    valueFrom:
      secretKeyRef:
        name: my-secrets
        key: api-key
```

### agentNetwork (optional)

Agent-to-Agent networking configuration.

#### agentNetwork.expose

Create a Kubernetes Service for this agent:

```yaml
agentNetwork:
  expose: true
```

When `true`, creates a Service that exposes:
- Port 80 → Container port 8000
- Endpoints: `/health`, `/ready`, `/.well-known/agent`, `/agent/invoke`, `/v1/chat/completions`

#### agentNetwork.access

List of agent names this agent can delegate to:

```yaml
agentNetwork:
  expose: true
  access:
  - worker-1
  - worker-2
```

The operator automatically:
1. Finds the referenced Agent resources
2. Waits for them to be Ready
3. Sets `PEER_AGENTS=worker-1,worker-2`
4. Sets `PEER_AGENT_WORKER_1_CARD_URL=http://worker-1...`
5. Sets `PEER_AGENT_WORKER_2_CARD_URL=http://worker-2...`

# TODO: remove as outlined above in favour of podspec
### replicas (optional)

Number of agent pod replicas:

```yaml
spec:
  replicas: 3
```

Default: 1

Note: Memory is per-pod and not shared between replicas.

# TODO: remove as outlined above in favour of podspec
### resources (optional)

Kubernetes resource requirements:

```yaml
spec:
  resources:
    requests:
      memory: "256Mi"
      cpu: "200m"
    limits:
      memory: "1Gi"
      cpu: "2000m"
```

# TODO: Add section on new podspec and how override works

## Status Fields

| Field | Type | Description |
|-------|------|-------------|
| `phase` | string | Current phase: Pending, Ready, Failed, Waiting |
| `ready` | bool | Whether agent is ready to serve |
| `observedReplicas` | int | Current replica count |
| `endpoint` | string | Service URL for A2A communication |
| `linkedResources` | map | References to dependencies |
| `message` | string | Additional status information |

## Examples

### Simple Agent

```yaml
apiVersion: ethical.institute/v1alpha1
kind: Agent
metadata:
  name: simple-agent
spec:
  modelAPI: ollama
  config:
    description: "A simple chat agent"
    instructions: "You are a helpful assistant."
  agentNetwork:
    expose: true
```

### Agent with Tools

```yaml
apiVersion: ethical.institute/v1alpha1
kind: Agent
metadata:
  name: tool-agent
spec:
  modelAPI: ollama
  mcpServers:
  - calculator
  - web-search
  config:
    description: "An agent with tools"
    instructions: |
      You have access to a calculator and web search.
      Use them when appropriate.
    agenticLoop:
      maxSteps: 5
      enableTools: true
  agentNetwork:
    expose: true
```

### Coordinator with Workers

```yaml
apiVersion: ethical.institute/v1alpha1
kind: Agent
metadata:
  name: coordinator
spec:
  modelAPI: ollama
  config:
    description: "Coordinator agent"
    instructions: |
      You coordinate worker agents.
      Delegate research to researcher.
      Delegate analysis to analyst.
    agenticLoop:
      maxSteps: 10
      enableDelegation: true
  agentNetwork:
    expose: true
    access:
    - researcher
    - analyst
```

### High-Availability Agent

```yaml
apiVersion: ethical.institute/v1alpha1
kind: Agent
metadata:
  name: ha-agent
spec:
  modelAPI: ollama
  replicas: 3
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2000m"
  config:
    description: "High-availability agent"
  agentNetwork:
    expose: true
```

# TODO: update docs with waitfordependencies attribute
## Troubleshooting

### Agent Stuck in Pending

```bash
kubectl describe agent my-agent -n my-namespace
```

Common causes:
- ModelAPI not Ready
- MCPServer not Ready
- Peer agent not Ready

### Agent Stuck in Failed

Check pod logs:

```bash
kubectl logs -l app=my-agent -n my-namespace
```

Common causes:
- Invalid MODEL_API_URL
- Model not available
- Image pull errors

### Sub-Agent Delegation Failing

Verify peer agent is accessible:

```bash
# Check if service exists
kubectl get svc worker-1 -n my-namespace

# Check agent card endpoint
kubectl exec -it deploy/coordinator -n my-namespace -- \
  curl http://worker-1/.well-known/agent
```
