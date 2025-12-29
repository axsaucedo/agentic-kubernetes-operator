"""HTTP server with A2A protocol support and OpenAI compatibility."""

import logging
import os
import time
import uuid
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import uvicorn

from modelapi.client import LiteLLM
from agent.client import Agent, RemoteAgent
from agent.memory import LocalMemory

logger = logging.getLogger(__name__)


class AgentServerSettings(BaseSettings):
    """Agent server configuration from environment variables."""

    # Required settings
    agent_name: str
    model_api_url: str
    model_name: str

    # Optional settings with defaults
    agent_description: str = "AI Agent"
    agent_instructions: str = "You are a helpful assistant."
    agent_port: int = 8000
    agent_log_level: str = "INFO"
    server_host: str = "0.0.0.0"

    # Tool and peer configuration
    mcp_servers: str = ""  # Comma-separated
    peer_agents: str = ""  # Comma-separated

    class Config:
        env_file = ".env"
        case_sensitive = False


class TaskRequest(BaseModel):
    """Request model for agent task invocation."""
    task: str


class AgentServer:
    """HTTP server that exposes agent via A2A protocol and OpenAI API."""

    def __init__(self, settings: AgentServerSettings = None, agent: Agent = None):
        """Initialize agent server.

        Args:
            settings: AgentServerSettings (created from env if not provided)
            agent: Pre-built Agent instance (created from settings if not provided)
        """
        self.settings = settings or AgentServerSettings()
        self.app = FastAPI(
            title=f"Agent: {self.settings.agent_name}",
            description=self.settings.agent_description
        )
        self.memory = LocalMemory()

        # Initialize agent if not provided
        if agent:
            self.agent = agent
        else:
            self.agent = self._create_agent()

        self._setup_routes()
        logger.info(f"AgentServer initialized for {self.settings.agent_name}")

    def _create_agent(self) -> Agent:
        """Create agent from settings.

        Returns:
            Configured Agent instance
        """
        logger.info(f"Creating agent: {self.settings.agent_name}")
        logger.info(f"Description: {self.settings.agent_description}")
        logger.info(f"Model API: {self.settings.model_api_url}")
        logger.info(f"Model: {self.settings.model_name}")

        # Initialize LiteLLM for model access
        llm = LiteLLM(
            model=self.settings.model_name,
            api_base=self.settings.model_api_url,
        )

        # Load MCP toolsets
        toolsets = []
        if self.settings.mcp_servers:
            logger.info(f"Loading MCP toolsets from: {self.settings.mcp_servers}")
            mcp_names = [s.strip() for s in self.settings.mcp_servers.split(",") if s.strip()]
            for name in mcp_names:
                env_key = f"MCP_SERVER_{name.upper()}_URL"
                url = os.getenv(env_key)
                if url:
                    try:
                        # Import MCPToolset lazily
                        from mcptools.client import MCPToolset
                        toolset = MCPToolset([url])
                        toolsets.append(toolset)
                        logger.info(f"Loaded MCP toolset: {name} -> {url}")
                    except ImportError:
                        logger.warning(f"MCPToolset not available, skipping {name}")
                    except Exception as e:
                        logger.error(f"Failed to load MCP toolset {name}: {e}")
                else:
                    logger.warning(f"MCP server {name} URL not found in {env_key}")

        # Load peer agents
        sub_agents = []
        if self.settings.peer_agents:
            logger.info(f"Loading peer agents from: {self.settings.peer_agents}")
            peer_names = [a.strip() for a in self.settings.peer_agents.split(",") if a.strip()]
            for name in peer_names:
                env_name = name.upper().replace("-", "_")
                env_key = f"PEER_AGENT_{env_name}_CARD_URL"
                agent_card_url = os.getenv(env_key)
                if agent_card_url:
                    remote_agent = RemoteAgent(name, agent_card_url)
                    sub_agents.append(remote_agent)
                    logger.info(f"Loaded peer agent: {name} -> {agent_card_url}")
                else:
                    logger.warning(f"Peer agent {name} card URL not found in {env_key}")

        # Create agent with all configuration
        agent = Agent(
            name=self.settings.agent_name,
            description=self.settings.agent_description,
            instructions=self.settings.agent_instructions,
            model_api=llm,
            tools=toolsets,
            sub_agents=sub_agents,
            memory=self.memory
        )

        logger.info("Agent created successfully")
        return agent

    def _setup_routes(self):
        """Setup HTTP routes."""

        @self.app.get("/health")
        async def health():
            """Health check endpoint for Kubernetes liveness probes."""
            return JSONResponse({
                "status": "healthy",
                "name": self.settings.agent_name
            })

        @self.app.get("/ready")
        async def ready():
            """Readiness check endpoint for Kubernetes readiness probes."""
            return JSONResponse({
                "status": "ready",
                "name": self.settings.agent_name
            })

        @self.app.get("/.well-known/agent")
        async def agent_card():
            """A2A agent discovery endpoint."""
            base_url = f"http://localhost:{self.settings.agent_port}"
            card = self.agent.get_agent_card(base_url)
            return JSONResponse(card.model_dump())

        @self.app.post("/agent/invoke")
        async def invoke_agent(task_request: TaskRequest):
            """A2A agent invocation endpoint."""
            try:
                response = await self.agent.process_message(task_request.task)
                return JSONResponse({"response": response})
            except Exception as e:
                logger.error(f"Agent invocation error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/v1/chat/completions")
        async def openai_chat_completions(request_data: dict):
            """OpenAI-compatible chat completions endpoint."""
            try:
                messages = request_data.get("messages", [])
                if not messages:
                    raise HTTPException(status_code=400, detail="No messages provided")

                # Convert to single prompt (simplified)
                user_message = messages[-1]["content"]

                response = await self.agent.process_message(user_message)

                return JSONResponse({
                    "id": f"chatcmpl-{uuid.uuid4().hex}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": request_data.get("model", self.settings.model_name),
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": response},
                        "finish_reason": "stop"
                    }]
                })
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"OpenAI endpoint error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    async def startup(self):
        """Initialize agent on startup."""
        logger.info("Starting up agent server")
        await self.agent.initialize()

    async def shutdown(self):
        """Cleanup on shutdown."""
        logger.info("Shutting down agent server")
        await self.agent.close()

    def run(self, host: str = None, port: int = None):
        """Run the server.

        Args:
            host: Host to bind to (default from settings)
            port: Port to bind to (default from settings)
        """
        host = host or self.settings.server_host
        port = port or self.settings.agent_port

        # Configure logging
        logging.basicConfig(level=self.settings.agent_log_level)

        # Add event handlers
        @self.app.on_event("startup")
        async def on_startup():
            await self.startup()

        @self.app.on_event("shutdown")
        async def on_shutdown():
            await self.shutdown()

        logger.info(f"Starting Agentic Runtime Server on {host}:{port}")
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level=self.settings.agent_log_level.lower()
        )


# Module-level app instance for direct import (backward compatibility)
# Only create if we have the required environment variables
import os
if all(os.getenv(k) for k in ["AGENT_NAME", "MODEL_API_URL", "MODEL_NAME"]):
    _settings = AgentServerSettings()
    _server = AgentServer(_settings)
    app = _server.app
else:
    # Create a minimal FastAPI app that will be replaced when actually used
    app = FastAPI(title="Agent Server (Not Configured)")


# Entry point
if __name__ == "__main__":
    settings = AgentServerSettings()
    server = AgentServer(settings)
    server.run()
