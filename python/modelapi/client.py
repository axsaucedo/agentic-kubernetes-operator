"""
ModelAPI client for OpenAI-compatible servers.

Clean, simple implementation following KEEP IT SIMPLE philosophy.
Supports both streaming and non-streaming with proper error handling.
"""

import json
import logging
from typing import Dict, List, Optional, AsyncIterator
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)


class ModelAPI:
    """Simple ModelAPI client for OpenAI-compatible servers."""

    def __init__(self, model: str, api_base: str, api_key: Optional[str] = None):
        """Initialize ModelAPI client.

        Args:
            model: Model name (e.g., "gpt-4o-mini", "smollm2:135m")
            api_base: API base URL (e.g., "http://localhost:8002")
            api_key: Optional API key for authentication
        """
        self.model = model
        self.api_base = api_base.rstrip('/')  # Clean trailing slash
        self.api_key = api_key

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.AsyncClient(
            base_url=self.api_base,
            headers=headers,
            timeout=60.0  # Longer timeout for LLM responses
        )

        logger.info(f"ModelAPI initialized: model={self.model}, api_base={self.api_base}")

    async def complete(self, messages: List[Dict]) -> Dict:
        """Non-streaming chat completion.

        Args:
            messages: OpenAI-format messages (e.g., [{"role": "user", "content": "Hello"}])

        Returns:
            OpenAI-format response dict

        Raises:
            httpx.HTTPError: For HTTP errors
            ValueError: For invalid responses
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        try:
            response = await self.client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()

            # Validate response structure
            if "choices" not in data or not data["choices"]:
                raise ValueError(f"Invalid response format: missing choices")

            return data

        except httpx.HTTPError as e:
            logger.error(f"HTTP error in completion: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in completion: {e}")
            raise ValueError(f"Invalid JSON response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in completion: {e}")
            raise

    async def stream(self, messages: List[Dict]) -> AsyncIterator[str]:
        """Streaming chat completion with proper SSE parsing.

        Args:
            messages: OpenAI-format messages

        Yields:
            Content chunks from the response

        Raises:
            httpx.HTTPError: For HTTP errors
            ValueError: For invalid responses
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }

        try:
            async with self.client.stream(
                "POST",
                "/v1/chat/completions",
                json=payload,
                headers={"Accept": "text/event-stream"}
            ) as response:
                response.raise_for_status()

                # Verify we got SSE content type
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" not in content_type:
                    logger.warning(f"Unexpected content-type for streaming: {content_type}")

                async for line in response.aiter_lines():
                    content = await self._parse_sse_line(line)
                    if content is not None:
                        yield content

        except httpx.HTTPError as e:
            logger.error(f"HTTP error in streaming: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in streaming: {e}")
            raise

    async def _parse_sse_line(self, line: str) -> Optional[str]:
        """Parse a single SSE line and extract content.

        Args:
            line: Raw SSE line from the stream

        Returns:
            Content string or None if line should be ignored
        """
        line = line.strip()

        # Skip empty lines
        if not line:
            return None

        # Handle SSE data lines
        if line.startswith("data: "):
            data_str = line[6:]  # Remove "data: " prefix

            # Check for stream end
            if data_str == "[DONE]":
                return None

            # Skip empty data
            if not data_str.strip():
                return None

            try:
                data = json.loads(data_str)

                # Extract content from OpenAI-format streaming response
                if "choices" in data and data["choices"]:
                    choice = data["choices"][0]
                    delta = choice.get("delta", {})

                    if "content" in delta:
                        return delta["content"]

                return None

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse SSE JSON: {data_str[:100]}... Error: {e}")
                return None

        # Skip non-data SSE lines (comments, etc.)
        return None

    async def close(self):
        """Close HTTP client and cleanup resources."""
        try:
            await self.client.aclose()
            logger.debug("ModelAPI client closed successfully")
        except Exception as e:
            logger.warning(f"Error closing ModelAPI client: {e}")


# Backwards compatibility classes for tests

@dataclass
class ModelMessage:
    """Backwards compatibility message model."""
    role: str
    content: str


@dataclass
class ModelResponse:
    """Backwards compatibility response model."""
    content: str
    finish_reason: str


# For backwards compatibility during migration
LiteLLM = ModelAPI