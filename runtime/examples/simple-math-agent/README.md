# Simple Math Agent - Local Example

This example demonstrates a simple AI agent that:
- Loads configuration from environment variables
- Connects to a local Ollama model API
- Uses MCP tools (calculator) for mathematical operations
- Performs mathematical reasoning with the language model

## Prerequisites

1. **Local Ollama Server** running with SmolLM2 model:
   ```bash
   ollama pull smollm2:135m
   ollama serve
   ```

2. **MCP Server** (calculator) running:
   ```bash
   pip install mcp-server-calculator
   uvx mcp-server-calculator  # or direct invocation
   ```

3. **Python 3.11+** with httpx library:
   ```bash
   pip install httpx
   ```

## Setup

1. Copy environment configuration:
   ```bash
   make setup
   ```

2. Edit `.env` file to point to your local services:
   ```
   MODEL_API_URL=http://localhost:11434/v1
   MCP_SERVER_MATH_TOOLS_URL=http://localhost:8001
   ```

## Running the Agent

```bash
make run
```

Or directly:
```bash
python3 agent.py
```

## Expected Output

The agent will:
1. Load configuration from `.env`
2. Connect to the Ollama model API
3. Fetch available tools from the MCP server
4. Send a math reasoning prompt to the model
5. Display the model's response

Example flow:
```
2025-12-26 10:30:45 - __main__ - INFO - Initialized agent: math-agent
2025-12-26 10:30:45 - __main__ - INFO - Model API URL: http://localhost:11434/v1
2025-12-26 10:30:45 - __main__ - INFO - MCP Servers: ['math-tools']
2025-12-26 10:30:45 - __main__ - INFO - Starting simple math agent example
2025-12-26 10:30:45 - __main__ - INFO - Agent: math-agent
2025-12-26 10:30:45 - __main__ - INFO - Description: A simple mathematical reasoning agent
2025-12-26 10:30:46 - __main__ - INFO - Loaded 5 tools from math-tools
2025-12-26 10:30:46 - __main__ - INFO - Sending prompt to model...
2025-12-26 10:31:10 - __main__ - INFO - Model response received (250 chars)
...
[Agent reasoning and calculation output]
...
```

## Troubleshooting

### Connection refused to Ollama
- Ensure Ollama is running: `ollama serve`
- Check Ollama is accessible: `curl http://localhost:11434/api/tags`
- If Docker Desktop, may need `host.docker.internal` instead of `localhost`

### MCP server not responding
- Ensure mcp-server-calculator is running
- Try: `pip install mcp-server-calculator && uvx mcp-server-calculator`
- Verify endpoint in `.env` matches where server is running

### Model "smollm2:135m" not found
- Pull the model: `ollama pull smollm2:135m`
- Or use another available model by editing the script

## Next Steps

This example serves as a baseline for:
- Testing agent runtime locally before Kubernetes deployment
- Validating MCP tool integration
- Ensuring model API connectivity
- Debugging agent behavior in isolation

See also:
- `../multi-agent-coordination/` - Multi-agent example with A2A communication
- `../../server/` - Full agent runtime server implementation
