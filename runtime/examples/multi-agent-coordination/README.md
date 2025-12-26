# Multi-Agent Coordination - Local Example

This example demonstrates Agent-to-Agent (A2A) communication where multiple agents coordinate to solve complex tasks:

**Agents**:
- **Coordinator**: Orchestrates tasks, delegates to specialized agents
- **Researcher**: Specializes in information gathering and analysis
- **Analyst**: Performs calculations using math MCP tools

**Capabilities**:
- Direct A2A HTTP communication via Agent Card endpoints
- Task delegation and result aggregation
- Access to shared model API
- Specialized tool access (analyst has math tools)

## Prerequisites

1. **Local Ollama Server** with SmolLM2:
   ```bash
   ollama pull smollm2:135m
   ollama serve
   ```

2. **MCP Math Server** running:
   ```bash
   pip install mcp-server-calculator
   uvx mcp-server-calculator
   ```

3. **Agent Runtime Server** available:
   - Implemented at `../../server/server.py`

4. **Python 3.11+** with required dependencies:
   ```bash
   pip install httpx
   ```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│        Shared Model API (Ollama SmolLM2)                │
│        http://localhost:11434/v1                        │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
    ┌───▼────┐  ┌───▼────┐  ┌───▼────┐
    │ Coord  │  │Research│  │Analyst │
    │ 8000   │  │ 8001   │  │ 8002   │
    └───┬────┘  └───────┘  └───┬───┘
        │                       │
        └─────────────A2A───────┘

Analyst also connects to:
    └─────MCP Math Server (localhost:8003)
```

## Setup

1. Copy environment configuration:
   ```bash
   make setup
   ```

2. Edit `.env` to match your local setup:
   - `MODEL_API_URL`: Ollama endpoint
   - Port mappings for each agent (8000, 8001, 8002)
   - MCP server endpoint

## Running the Example

```bash
make run
```

This will:
1. Start the Coordinator agent (port 8000)
2. Start the Researcher agent (port 8001)
3. Start the Analyst agent (port 8002)
4. Wait for all agents to be ready
5. Run coordination tests:
   - Coordinator delegates a math task to the Analyst
   - Coordinator delegates a research task to the Researcher
6. Stop all agents

## Expected Output

```
2025-12-26 10:45:00 - orchestrate - INFO - Setting up multi-agent system...
2025-12-26 10:45:00 - orchestrate - INFO - Starting coordinator agent on port 8000...
2025-12-26 10:45:01 - orchestrate - INFO - Starting researcher agent on port 8001...
2025-12-26 10:45:02 - orchestrate - INFO - Starting analyst agent on port 8002...
2025-12-26 10:45:03 - orchestrate - INFO - All agents started successfully
2025-12-26 10:45:04 - orchestrate - INFO - Starting coordination test...
2025-12-26 10:45:04 - orchestrate - INFO - Test 1: Coordinator delegating math task to analyst...
2025-12-26 10:45:20 - orchestrate - INFO - Coordinator result:
[Agent reasoning about math task using analyst's capabilities]
2025-12-26 10:45:22 - orchestrate - INFO - Test 2: Coordinator delegating research task to researcher...
2025-12-26 10:45:38 - orchestrate - INFO - Coordinator result:
[Agent reasoning about research task using researcher's capabilities]
2025-12-26 10:45:40 - orchestrate - INFO - Cleaning up agents...
```

## Troubleshooting

### "Connection refused" errors
- Ensure Ollama is running: `ollama serve`
- Ensure MCP server is running: `uvx mcp-server-calculator`
- Check `.env` port mappings match your setup

### Agent fails to start
- Verify `runtime/server/server.py` is implemented and accessible
- Check Python environment has all dependencies (httpx, etc.)
- Review agent logs for specific errors

### A2A communication fails
- Verify agent Card endpoints are correct in `.env`
- Ensure agents are running and responding to health checks
- Check network connectivity between localhost ports

## A2A Communication Details

### Agent Card Endpoint
Each agent exposes `/agent/card` endpoint that returns:
```json
{
  "name": "coordinator",
  "description": "Orchestrates tasks",
  "tools": [...],
  "capabilities": [...]
}
```

### Task Invocation
Send tasks to `/agent/invoke`:
```
POST /agent/invoke
Content-Type: application/json

{"task": "Calculate 2+2"}
```

Returns:
```json
{
  "result": "The answer is 4"
}
```

## Next Steps

This example demonstrates:
- ✅ Local agent lifecycle management
- ✅ Multi-agent coordination
- ✅ A2A communication patterns
- ✅ Task delegation

For production use in Kubernetes, see:
- `../../operator/config/samples/multi_agent_example.yaml`
- `../../tests/e2e_k8s_test.py`

## Performance Notes

- First invocation will be slower (model warming up)
- Subsequent calls are faster as model context persists
- Network latency between agents is minimal on localhost
- In Kubernetes, DNS-based service discovery replaces hardcoded IPs
