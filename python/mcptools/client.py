import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pydantic_settings import BaseSettings
import httpx

logger = logging.getLogger(__name__)


class MCPClientSettings(BaseSettings):
    # Required settings
    mcp_client_host: str
    mcp_client_port: str
    # Optional settings
    mcp_client_endpoint: str = "/mcp/tools"

@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]

    def __str__(self) -> str:
        return f"Tool({self.name}: {self.description})"


class MCPClient:
    def __init__(self, settings: MCPClientSettings):
        self._url = f"{settings.mcp_client_host}:{settings.mcp_client_port}{settings.mcp_client_endpoint}"
        self._tools = {}

        # HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5))

        logger.info(f"MCPClient initialized with settings: {settings}")

    async def discover_tools(self) -> None:
        response = await self.client.get(self._url)
        response.raise_for_status()
        tools_payload = response.json()

        if isinstance(tools_payload, list):
            tools_list = tools_payload
        elif isinstance(tools_payload, dict):
            tools_list = tools_payload.get("tools", [])
        else:
            raise ValueError(f"Invalid tools response format: {type(tools_payload)}")

        for tool_data in tools_list:
            try:
                tool = Tool(
                    name=tool_data["name"],
                    description=tool_data["description"],
                    parameters=tool_data["parameters"])
                self._tools[tool_data["name"]] = tool
            except Exception as e:
                logger.warning(f"Failed to parse tool: {tool_data}, error: {e}")

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        if not name in self._tools:
            raise ValueError(f"Tool '{name}' not found. Available tools: {self._tools.keys()}")

        response = await self.client.post(self._url, json={"tool": name, "arguments": args})
        response.raise_for_status()

        return response.json()

    def get_tools(self) -> List[Tool]:
        return list(self._tools.keys())

    async def close(self):
        try:
            await self.client.aclose()
            logger.debug("MCPClient closed successfully")
        except Exception as e:
            logger.warning(f"Error closing MCPClient: {e}")

