"""
Agentic Runtime Server using Google ADK Native Multi-Agent Support

This server exposes an agent using Google ADK's native A2A protocol.
Each agent can:
- Execute with LiteLlm model access
- Use MCP tools via McpToolset
- Coordinate with peer agents via RemoteA2aAgent
"""

import json
import logging
from typing import List

from pydantic_settings import BaseSettings
from starlette.responses import JSONResponse

from google.adk.agents.llm_agent import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset


class AgentSettings(BaseSettings):
    """Agent configuration from environment variables."""

    # Required settings (no defaults)
    agent_name: str
    model_api_url: str
    model_name: str

    # Optional settings with defaults
    agent_description: str = "Agent"
    agent_instructions: str = "You are a helpful assistant."
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    agent_log_level: str = "INFO"

    # Optional lists
    mcp_servers: str = ""  # Comma-separated list
    peer_agents: str = ""  # Comma-separated list

    class Config:
        env_file = ".env"
        case_sensitive = False


# Configure logging
settings = AgentSettings()
logging.basicConfig(level=settings.agent_log_level)
logger = logging.getLogger(__name__)

# Suppress uvicorn access logs
logging.getLogger("uvicorn.access").disabled = True


def load_mcp_toolsets() -> List:
    """Load MCP toolsets from environment variables."""
    toolsets = []
    mcp_names = [s.strip() for s in settings.mcp_servers.split(",") if s.strip()]

    for name in mcp_names:
        env_key = f"MCP_SERVER_{name.upper()}_URL"
        # Get URL from settings by manually checking environment
        import os
        url = os.getenv(env_key)

        if url:
            try:
                toolset = McpToolset(mcp_server_urls=[url])
                toolsets.append(toolset)
                logger.info(f"Loaded MCP toolset: {name} -> {url}")
            except Exception as e:
                logger.error(f"Failed to load MCP toolset {name}: {e}")
        else:
            logger.warning(f"MCP server {name} referenced but URL not found in {env_key}")

    return toolsets


def load_peer_agents() -> List[RemoteA2aAgent]:
    """Load peer agent configurations from environment variables."""
    peer_agents = []
    peer_names = [a.strip() for a in settings.peer_agents.split(",") if a.strip()]

    import os
    for name in peer_names:
        # Convert name to valid env var format (uppercase, replace hyphens with underscores)
        env_name = name.upper().replace("-", "_")
        env_key = f"PEER_AGENT_{env_name}_CARD_URL"
        agent_card_url = os.getenv(env_key)

        if agent_card_url:
            remote_agent = RemoteA2aAgent(
                name=name.replace("-", "_"),
                description=f"Delegate tasks to {name} agent",
                agent_card=agent_card_url,
            )
            peer_agents.append(remote_agent)
            logger.info(f"Loaded peer agent: {name} -> {agent_card_url}")
        else:
            logger.warning(f"Peer agent {name} referenced but card URL not found in {env_key}")

    return peer_agents


def create_agent() -> Agent:
    """Create and configure the agent using Google ADK.

    Loads all sub-agents first before creating the main agent to ensure
    the agent is initialized with complete configuration.
    """
    logger.info(f"Creating agent: {settings.agent_name}")
    logger.info(f"Description: {settings.agent_description}")
    logger.info(f"Model API: {settings.model_api_url}")
    logger.info(f"Model: {settings.model_name}")

    # Initialize LiteLlm for model access
    llm = LiteLlm(
        model=settings.model_name,
        api_base=settings.model_api_url,
    )

    # Load MCP toolsets - pass directly to agent
    mcp_toolsets = []
    if settings.mcp_servers:
        logger.info(f"Loading MCP toolsets from: {settings.mcp_servers}")
        mcp_toolsets = load_mcp_toolsets()
        logger.info(f"Loaded {len(mcp_toolsets)} MCP toolsets")

    # Load peer agents BEFORE creating the main agent
    sub_agents = []
    if settings.peer_agents:
        logger.info(f"Loading peer agents from: {settings.peer_agents}")
        sub_agents = load_peer_agents()
        logger.info(f"Loaded {len(sub_agents)} peer agents")

    # Create agent with all configuration at once
    # Pass MCP toolsets directly - ADK handles empty list gracefully
    # Replace hyphens with underscores in agent name (ADK requires valid Python identifiers)
    agent = Agent(
        name=settings.agent_name.replace("-", "_"),
        model=llm,
        instruction=settings.agent_instructions,
        tools=mcp_toolsets,
        sub_agents=sub_agents,
    )

    logger.info("Agent created successfully")
    return agent


# Create the agent and expose it via A2A
agent = create_agent()
app = to_a2a(agent)

# Add Kubernetes health check endpoints directly to Starlette app
@app.route("/health")
async def health(request):
    """Health check endpoint for Kubernetes liveness probes."""
    return JSONResponse({"status": "healthy", "name": settings.agent_name})

@app.route("/ready")
async def ready(request):
    """Readiness check endpoint for Kubernetes readiness probes."""
    return JSONResponse({"status": "ready", "name": settings.agent_name})


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Agentic Runtime Server on {settings.server_host}:{settings.server_port}")
    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.agent_log_level.lower()
    )
