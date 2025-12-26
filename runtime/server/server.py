"""
Agentic Agent Runtime Server using Google's ADK.

This server loads configuration entirely from environment variables and
exposes a long-running HTTP API for agent operations including:
- Agent Card endpoint for A2A communication
- Tool execution endpoints
- Health check endpoints
"""

import os
import logging
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Agentic Runtime",
    description="Agent Runtime Server for Agentic Kubernetes Operator",
    version="0.1.0"
)


class AgentConfig(BaseModel):
    """Agent configuration from environment"""
    name: str
    description: str
    instructions: str
    model_api_url: str
    model_api_key: Optional[str] = None
    mcp_servers: list[str] = []
    peer_agents: list[str] = []


def load_config() -> AgentConfig:
    """Load configuration from environment variables"""
    return AgentConfig(
        name=os.getenv("AGENT_NAME", "default-agent"),
        description=os.getenv("AGENT_DESCRIPTION", "Default agent"),
        instructions=os.getenv("AGENT_INSTRUCTIONS", "You are a helpful assistant."),
        model_api_url=os.getenv("MODEL_API_URL", "http://localhost:8000"),
        model_api_key=os.getenv("MODEL_API_KEY"),
        mcp_servers=[s.strip() for s in os.getenv("MCP_SERVERS", "").split(",") if s.strip()],
        peer_agents=[a.strip() for a in os.getenv("PEER_AGENTS", "").split(",") if a.strip()],
    )


@app.on_event("startup")
async def startup_event():
    """Initialize agent on startup"""
    logger.info("Starting Agentic Runtime Server...")
    config = load_config()
    logger.info(f"Agent: {config.name}")
    logger.info(f"Model API: {config.model_api_url}")
    if config.mcp_servers:
        logger.info(f"MCP Servers: {config.mcp_servers}")
    if config.peer_agents:
        logger.info(f"Peer Agents: {config.peer_agents}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready"}


@app.get("/agent/card")
async def get_agent_card() -> Dict[str, Any]:
    """
    Agent Card endpoint for A2A communication.

    This endpoint is used by other agents to discover and communicate
    with this agent via A2A (Agent-to-Agent) protocol.
    """
    config = load_config()
    return {
        "name": config.name,
        "description": config.description,
        "endpoint": f"http://localhost:8000",  # TODO: get from environment
        "capabilities": {
            "tools": [s for s in config.mcp_servers],
            "model": config.model_api_url,
        }
    }


@app.post("/agent/invoke")
async def invoke_agent(request: Dict[str, Any]):
    """
    Invoke the agent with a request.

    Request format:
    {
        "prompt": "user prompt",
        "tools": ["tool1", "tool2"],
        ...
    }
    """
    # TODO: Implement agent invocation
    raise HTTPException(status_code=501, detail="Agent invocation not yet implemented")


@app.post("/tools/execute")
async def execute_tool(request: Dict[str, Any]):
    """
    Execute a tool on this agent.

    Request format:
    {
        "tool_name": "math.add",
        "tool_input": {...}
    }
    """
    # TODO: Implement tool execution
    raise HTTPException(status_code=501, detail="Tool execution not yet implemented")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
