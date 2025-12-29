"""MCP client for tool consumption by agents."""

import httpx
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MCPTool(BaseModel):
    """Represents a single MCP tool/resource."""
    name: str
    description: str
    parameters: Dict[str, Any] = {}


class MCPToolset:
    """MCP client that can interact with standard MCP servers."""

    def __init__(self, mcp_server_urls: List[str]):
        """Initialize MCPToolset with list of server URLs.

        Args:
            mcp_server_urls: List of MCP server URLs to connect to
        """
        self.server_urls = mcp_server_urls
        self._tools: List[MCPTool] = []
        self._clients = {}
        logger.info(f"MCPToolset initialized with {len(mcp_server_urls)} servers")

    async def discover_tools(self) -> List[MCPTool]:
        """Discover available tools from MCP servers.

        Returns:
            List of MCPTool instances
        """
        all_tools = []
        for url in self.server_urls:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{url}/tools")
                    if response.status_code == 200:
                        tools_data = response.json()
                        if isinstance(tools_data, list):
                            for tool_data in tools_data:
                                try:
                                    tool = MCPTool(**tool_data)
                                    all_tools.append(tool)
                                    logger.debug(f"Discovered tool: {tool.name}")
                                except Exception as e:
                                    logger.warning(f"Failed to parse tool: {e}")
                        elif isinstance(tools_data, dict):
                            # Handle case where tools are wrapped in a dict
                            tools_list = tools_data.get("tools", [])
                            for tool_data in tools_list:
                                try:
                                    tool = MCPTool(**tool_data)
                                    all_tools.append(tool)
                                    logger.debug(f"Discovered tool: {tool.name}")
                                except Exception as e:
                                    logger.warning(f"Failed to parse tool: {e}")
            except Exception as e:
                logger.warning(f"Failed to discover tools from {url}: {e}")

        self._tools = all_tools
        logger.info(f"Discovered {len(all_tools)} total tools")
        return all_tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool via MCP protocol.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Result from tool execution

        Raises:
            Exception if tool not found or call fails
        """
        for url in self.server_urls:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{url}/call",
                        json={"tool": tool_name, "arguments": arguments},
                    )
                    if response.status_code == 200:
                        result_data = response.json()
                        logger.debug(f"Tool {tool_name} returned: {result_data}")
                        return result_data.get("result", result_data)
            except Exception as e:
                logger.warning(f"Tool call failed on {url}: {e}")
                continue

        raise Exception(f"Tool {tool_name} not found or failed on all servers")

    def get_tools(self) -> List[MCPTool]:
        """Get list of available tools.

        Returns:
            List of discovered MCPTool instances
        """
        return self._tools

    async def close(self):
        """Close HTTP clients and cleanup resources."""
        # Close any stored clients
        for client in self._clients.values():
            if hasattr(client, 'aclose'):
                try:
                    await client.aclose()
                except Exception as e:
                    logger.warning(f"Failed to close client: {e}")
        logger.debug("MCPToolset closed")
