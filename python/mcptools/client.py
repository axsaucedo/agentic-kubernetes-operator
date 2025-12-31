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
    """MCP client with graceful degradation for unavailable servers."""
    
    TIMEOUT = 5.0  # Short timeout - MCP servers should respond quickly

    def __init__(self, settings: MCPClientSettings):
        self._url = f"{settings.mcp_client_host}:{settings.mcp_client_port}{settings.mcp_client_endpoint}"
        self._tools: Dict[str, Tool] = {}
        self._active = False
        self._client = httpx.AsyncClient(timeout=self.TIMEOUT)
        logger.info(f"MCPClient initialized: {self._url}")

    async def _init(self) -> bool:
        """Discover tools and activate. Returns True if successful."""
        try:
            response = await self._client.get(self._url)
            response.raise_for_status()
            tools_payload = response.json()

            tools_list = tools_payload if isinstance(tools_payload, list) else tools_payload.get("tools", [])
            
            self._tools = {}
            for tool_data in tools_list:
                try:
                    self._tools[tool_data["name"]] = Tool(
                        name=tool_data["name"],
                        description=tool_data["description"],
                        parameters=tool_data["parameters"]
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse tool {tool_data}: {e}")
            
            self._active = True
            logger.info(f"MCPClient active with {len(self._tools)} tools")
            return True
        except Exception as e:
            self._active = False
            logger.warning(f"MCPClient init failed: {type(e).__name__}: {e}")
            return False

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """Call a tool. Re-inits if inactive. Raises RuntimeError on failure."""
        if not self._active:
            if not await self._init():
                raise RuntimeError(f"MCP server unavailable at {self._url}")

        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found. Available: {list(self._tools.keys())}")

        try:
            response = await self._client.post(self._url, json={"tool": name, "arguments": args})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._active = False
            raise RuntimeError(f"Tool {name}: {type(e).__name__}: {e}")

    def get_tools(self) -> List[Tool]:
        return list(self._tools.values())

    async def close(self):
        """Close HTTP client."""
        try:
            await self._client.aclose()
        except Exception:
            pass
