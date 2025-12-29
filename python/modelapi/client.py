"""LiteLLM client wrapper for OpenAI-compatible model access."""

import json
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
import httpx
from pydantic import BaseModel
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class ModelMessage(BaseModel):
    """Message model for chat completion."""
    role: str
    content: str


class ModelResponse(BaseModel):
    """Response model from chat completion."""
    content: str
    finish_reason: str


class ModelAPISettings(BaseSettings):
    """Model API configuration from environment variables."""
    model_api_url: str
    model_name: str
    api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False


class LiteLLM:
    """LiteLLM client for OpenAI-compatible model access."""

    def __init__(self, model: str = None, api_base: str = None, api_key: str = None):
        """Initialize LiteLLM client.

        Args:
            model: Model name (e.g., "gpt-3.5-turbo", "smollm2:135m")
            api_base: API base URL (e.g., "http://localhost:11434/v1")
            api_key: Optional API key for authentication
        """
        # Try to load settings from environment, but don't require them
        try:
            settings = ModelAPISettings()
            self.model = model or settings.model_name
            self.api_base = api_base or settings.model_api_url
            self.api_key = api_key or settings.api_key
        except Exception:
            # If settings can't be loaded from env, use provided parameters
            self.model = model or "default"
            self.api_base = api_base or "http://localhost:8000"
            self.api_key = api_key

        # Build headers
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.AsyncClient(
            base_url=self.api_base,
            headers=headers,
            timeout=30.0
        )
        logger.info(f"LiteLLM initialized with model={self.model}, api_base={self.api_base}")

    async def chat_completion(
        self,
        messages: List[ModelMessage],
        stream: bool = False
    ) -> ModelResponse:
        """Generate chat completion.

        Args:
            messages: List of messages in conversation
            stream: Whether to stream the response

        Returns:
            ModelResponse with content and finish_reason
        """
        if stream:
            return self._stream_completion(messages)
        else:
            return await self._complete_sync(messages)

    async def _complete_sync(self, messages: List[ModelMessage]) -> ModelResponse:
        """Non-streaming chat completion.

        Args:
            messages: List of messages

        Returns:
            ModelResponse with complete content
        """
        payload = {
            "model": self.model,
            "messages": [msg.model_dump() for msg in messages],
            "stream": False
        }

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()
            choice = data["choices"][0]

            return ModelResponse(
                content=choice["message"]["content"],
                finish_reason=choice.get("finish_reason", "stop")
            )
        except Exception as e:
            logger.error(f"Chat completion error: {e}")
            raise

    async def _stream_completion(self, messages: List[ModelMessage]) -> AsyncIterator[str]:
        """Streaming chat completion using server-sent events.

        Args:
            messages: List of messages

        Yields:
            Content chunks from the response
        """
        payload = {
            "model": self.model,
            "messages": [msg.model_dump() for msg in messages],
            "stream": True
        }

        try:
            async with self.client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        if data_str.strip() and data_str != "[DONE]":
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and data["choices"]:
                                    delta = data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"Stream completion error: {e}")
            raise

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
        logger.debug("LiteLLM client closed")
