"""
AgentServer implementation following Google ADK patterns.

Clean FastAPI server with health probes, A2A protocol, and OpenAI-compatible endpoints.
Supports both streaming and non-streaming responses.
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import uvicorn

from modelapi.client import ModelAPI
from agent.client import Agent
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

    class Config:
        env_file = ".env"
        case_sensitive = False


class TaskRequest(BaseModel):
    """A2A task request model."""
    task: str


class ChatCompletionRequest(BaseModel):
    """OpenAI chat completion request model."""
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    stream: Optional[bool] = False
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None


class AgentServer:
    """Simple AgentServer following Google ADK patterns."""

    def __init__(self, agent: Agent, port: int = 8000):
        """Initialize AgentServer with an agent (like Google ADK pattern).

        Args:
            agent: Agent instance to serve
            port: Port to serve on
        """
        self.agent = agent
        self.port = port

        # Create FastAPI app
        self.app = FastAPI(
            title=f"Agent: {agent.name}",
            description=agent.description,
            lifespan=self._lifespan
        )

        self._setup_routes()
        logger.info(f"AgentServer initialized for {agent.name} on port {port}")

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """Manage agent lifecycle."""
        logger.info("AgentServer startup")
        yield
        logger.info("AgentServer shutdown")
        await self.agent.close()

    def _setup_routes(self):
        """Setup HTTP routes for health, A2A, and OpenAI endpoints."""

        @self.app.get("/health")
        async def health():
            """Health check endpoint for Kubernetes liveness probes."""
            return JSONResponse({
                "status": "healthy",
                "name": self.agent.name,
                "timestamp": int(time.time())
            })

        @self.app.get("/ready")
        async def ready():
            """Readiness check endpoint for Kubernetes readiness probes."""
            return JSONResponse({
                "status": "ready",
                "name": self.agent.name,
                "timestamp": int(time.time())
            })

        @self.app.get("/.well-known/agent")
        async def agent_card():
            """A2A agent discovery endpoint."""
            base_url = f"http://localhost:{self.port}"
            card = self.agent.get_agent_card(base_url)
            return JSONResponse(card.to_dict())

        @self.app.post("/agent/invoke")
        async def invoke_agent(task_request: TaskRequest):
            """A2A agent invocation endpoint."""
            try:
                # Get first (and should be only) response chunk
                response_text = ""
                async for chunk in self.agent.process_message(task_request.task):
                    response_text += chunk

                return JSONResponse({
                    "response": response_text,
                    "status": "completed"
                })

            except Exception as e:
                logger.error(f"Agent invocation error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/v1/chat/completions")
        async def chat_completions(request: Request):
            """OpenAI-compatible chat completions endpoint (streaming + non-streaming)."""
            try:
                body = await request.json()

                messages = body.get("messages", [])
                if not messages:
                    raise HTTPException(status_code=400, detail="messages are required")

                model_name = body.get("model", "agent")
                stream_requested = body.get("stream", False)

                # Extract user message (simple approach)
                user_content = ""
                for msg in messages:
                    if msg.get("role") == "user":
                        user_content = msg.get("content", "")

                if not user_content:
                    raise HTTPException(status_code=400, detail="No user message found")

                if stream_requested:
                    return await self._stream_chat_completion(user_content, model_name)
                else:
                    return await self._complete_chat_completion(user_content, model_name)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Chat completion error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    async def _complete_chat_completion(self, user_message: str, model_name: str) -> JSONResponse:
        """Handle non-streaming chat completion."""
        # Collect complete response
        response_content = ""
        async for chunk in self.agent.process_message(user_message, stream=False):
            response_content += chunk

        return JSONResponse({
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,  # Not counting for simplicity
                "completion_tokens": 0,
                "total_tokens": 0
            }
        })

    async def _stream_chat_completion(self, user_message: str, model_name: str) -> StreamingResponse:
        """Handle streaming chat completion with SSE."""

        async def generate_stream():
            """Generate SSE stream for OpenAI-compatible streaming."""
            try:
                chat_id = f"chatcmpl-{uuid.uuid4().hex}"
                created_at = int(time.time())

                # Stream response chunks
                async for chunk in self.agent.process_message(user_message, stream=True):
                    if chunk:  # Only send non-empty chunks
                        sse_data = {
                            "id": chat_id,
                            "object": "chat.completion.chunk",
                            "created": created_at,
                            "model": model_name,
                            "choices": [{
                                "index": 0,
                                "delta": {
                                    "content": chunk
                                },
                                "finish_reason": None
                            }]
                        }

                        # Format as SSE
                        yield f"data: {str(sse_data).replace('None', 'null').replace(chr(39), chr(34))}\n\n"

                # Send final chunk to indicate completion
                final_data = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created_at,
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {str(final_data).replace('None', 'null').replace(chr(39), chr(34))}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                error_data = {
                    "error": {
                        "type": "server_error",
                        "message": str(e)
                    }
                }
                yield f"data: {str(error_data).replace(chr(39), chr(34))}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            }
        )

    def create_app(self) -> FastAPI:
        """Create FastAPI app (like Google ADK pattern).

        Returns:
            FastAPI application
        """
        return self.app

    def run(self, host: str = "0.0.0.0"):
        """Run the server.

        Args:
            host: Host to bind to
        """
        logger.info(f"Starting AgentServer on {host}:{self.port}")
        uvicorn.run(self.app, host=host, port=self.port)


def create_agent_server(settings: AgentServerSettings = None) -> AgentServer:

    if not settings:
        settings = AgentServerSettings()

    model_api = ModelAPI(
        model=settings.model_name,
        api_base=settings.model_api_url
    )

    agent = Agent(
        name=settings.agent_name,
        description=settings.agent_description,
        instructions=settings.agent_instructions,
        model_api=model_api
    )

    server = AgentServer(agent, port=settings.agent_port)

    logger.info(f"Created agent server: {settings.agent_name}")
    return server


def create_app(settings: AgentServerSettings = None) -> FastAPI:
    _server = create_agent_server()
    app = _server.create_app()
    logger.info(f"Created Agent FastAPI App")
    return app

