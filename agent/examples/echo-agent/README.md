# Echo Agent - MCP Tool Integration Test

This example tests the agent runtime with MCP (Model Context Protocol) tool integration by:
- Starting `agent/server/server.py` as a subprocess via uvicorn
- Configuring it entirely via environment variables
- Making HTTP requests to test agent endpoints
- Verifying MCP tool loading and execution
- Testing agent integration with echo tool

This is an **end-to-end test of production code** that exactly mimics what happens in Kubernetes.

## What It Demonstrates

- ✅ Agent runtime with MCP server integration
- ✅ Tool discovery from remote MCP servers
- ✅ Agent Card endpoint for tool listing (A2A discovery)
- ✅ Model API connectivity (Ollama)
- ✅ LLM reasoning with MCP tools
- ✅ Agent HTTP endpoints and lifecycle

## Prerequisites

1. **Local Ollama Server** running with SmolLM2 model:
   ```bash
   ollama pull smollm2:135m  # HuggingFaceTB/SmolLM2-135M-Instruct
   ollama serve
   ```

2. **MCP HTTP Wrapper** running on port 8002:
   ```bash
   PORT=8002 python mcp_http_wrapper.py
   ```
   This provides HTTP wrapper around MCP tools (bridges MCP protocol to simple HTTP REST)

3. **Python 3.12+** with required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Setup

1. Copy environment configuration:
   ```bash
   make setup
   ```

2. Optional: Edit `.env` to customize ports or MCP server URLs:
   ```
   AGENT_PORT=8001
   AGENT_NAME=echo-agent
   MODEL_API_URL=http://localhost:11434/v1
   MODEL_NAME=smollm2:135m
   MCP_SERVERS=echo_server
   MCP_SERVER_ECHO_SERVER_URL=http://localhost:8002
   ```

## Running the Test

```bash
make run
```

Or directly:
```bash
python3 agent.py
```

## What This Test Does

1. **Starts server.py**: Spawns `agent/server/server.py` on port 8001 via uvicorn
2. **Waits for readiness**: Polls `/ready` endpoint until server responds
3. **Gets Agent Card**: Retrieves agent capabilities via `/agent/card` (discovers available tools)
4. **Lists Tools**: Verifies 1 echo tool is available from MCP server
5. **Invokes agent**: Sends an echo task to `/agent/invoke` endpoint
6. **Verifies response**: Displays the agent's response
7. **Cleans up**: Terminates the server process

## Expected Output

```
============================================================
Echo Agent - End-to-End Test
============================================================

Test 1: Agent Card Discovery
----------------------------------------
2025-12-27 12:45:29 - __main__ - INFO - Agent card: echo-agent
2025-12-27 12:45:29 - __main__ - INFO -   Description: A simple echo agent for testing MCP integration
2025-12-27 12:45:29 - __main__ - INFO -   Tools: 1 available
2025-12-27 12:45:29 - __main__ - INFO -   Capabilities: {'model_reasoning': True, 'tool_use': True}

Test 2: Echo Tool Task
----------------------------------------
2025-12-27 12:45:29 - __main__ - INFO - Invoking agent with task: Use the echo tool...
2025-12-27 12:45:29 - INFO:server - Loaded 1 tools from echo_server
2025-12-27 12:45:29 - INFO:mcp_tools - Loaded 1 tools from echo_server

============================================================
`echo -n Hello, from the echo agent!\r`
============================================================
```

## Troubleshooting

### "Connection refused" errors
- Ensure Ollama is running: `ollama serve`
- Ensure model is available: `ollama list | grep smollm2`
- Ensure MCP HTTP wrapper is running: `PORT=8002 python mcp_http_wrapper.py`
- Ensure dependencies installed: `pip install -r requirements.txt`

### "Server did not become ready in time"
- Check Ollama connectivity: `curl http://localhost:11434/api/tags`
- Check if port 8001 is already in use: `lsof -i :8001`
- Check if MCP wrapper (8002) is in use: `lsof -i :8002`
- Review server logs for startup errors

### "Failed to get agent response"
- Verify model is loaded: `ollama list | grep smollm2`
- Check Ollama model API: `curl -X POST http://localhost:11434/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"smollm2:135m","messages":[{"role":"user","content":"test"}]}'`
- Check MCP wrapper endpoint: `curl http://localhost:8002/tools`

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Echo Agent Test Script (agent.py)               │
│                    - Runs on port 8001                       │
│                    - Loads .env configuration                │
│                    - Makes HTTP requests                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┬──────────────┐
        │                             │              │
        ▼                             ▼              ▼
┌─────────────────┐  ┌──────────────────────┐ ┌──────────────┐
│  Agent Server   │  │ MCP HTTP Wrapper     │ │   Ollama     │
│ (port 8001)     │  │ (port 8002)          │ │ (port 11434) │
│ - FastAPI       │  │ - Provides /tools    │ │ - SmolLM2    │
│ - Loads tools   │  │ - Echo tool def      │ │ - OpenAI API │
│ - Invokes agent │  │ - HTTP bridge for MCP│ │ - LLM API    │
└─────────────────┘  └──────────────────────┘ └──────────────┘
```

## Kubernetes Equivalent

This test uses the exact same `agent/server/server.py` that runs in Kubernetes:

| Local | Kubernetes |
|-------|-----------|
| Python subprocess + uvicorn | Pod with `python -m uvicorn server:app` |
| Environment variables in dict | Pod environment variables from Deployment |
| localhost:8001 | Service endpoint `agent-echo.default.svc.cluster.local` |
| Subprocess stdout/stderr | Pod logs via `kubectl logs` |
| Cleanup with terminate() | Pod lifecycle managed by ReplicaSet |

## Success Criteria

This test successfully validates that:
- ✅ Server starts with environment variable configuration
- ✅ Agent Card endpoint works (A2A discovery with tool listing)
- ✅ Model API connectivity established (Ollama)
- ✅ MCP tool loading works (1 echo tool discovered)
- ✅ MCP tools are usable by agent
- ✅ Agent reasoning completes successfully
- ✅ HTTP endpoints respond correctly with expected status codes

## Files in This Directory

- `agent.py` - Main test runner script
- `mcp_http_wrapper.py` - HTTP to MCP protocol bridge (for testing)
- `.env` - Environment configuration for test
- `.env.example` - Template environment configuration
- `requirements.txt` - Python dependencies
- `README.md` - This file
- `Makefile` - Build automation

## Next Steps

After validating the echo agent locally:

1. **Multi-Agent Testing** - See `../multi-agent-coordination/`
   - Multiple agents with A2A communication
   - More complex tool interactions

2. **Kubernetes Deployment** - Deploy to K8s:
   - Use `../../operator/config/samples/echo-agent.yaml` manifest
   - Same echo-agent but deployed as K8s resources
   - Services handle inter-pod communication
   - Verify scaling and resilience

3. **Real MCP Protocol Support**
   - Current wrapper is temporary HTTP bridge
   - Future: Support full MCP protocol in mcp_tools.py
   - Enable native MCP server integration

## Notes

- SmolLM2-135M is used for fast feedback (no GPU required)
- MCP HTTP wrapper is a temporary bridge for testing
- Production would use proper MCP client library
- All configuration via environment variables for easy Kubernetes integration
