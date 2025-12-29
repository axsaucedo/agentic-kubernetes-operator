"""
MCPClient for tool discovery and execution via MCP protocol.

Clean, simple implementation with proper error handling and connection pooling.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """Represents a discoverable tool from an MCP server."""
    name: str
    description: str
    parameters: Dict[str, Any]
    server_url: str  # Track which server provides this tool

    def __str__(self) -> str:
        return f"Tool({self.name}: {self.description})"


class MCPClient:
    """Simple MCP client for tool discovery and execution."""

    def __init__(self, server_urls: List[str] = None, mcp_server_urls: List[str] = None):
        """Initialize MCP client with server URLs.

        Args:
            server_urls: List of MCP server URLs to connect to
            mcp_server_urls: Legacy parameter name for backwards compatibility

        Raises:
            ValueError: If no server URLs provided or contains invalid URLs
        """
        # Support both old and new parameter names for backwards compatibility
        urls = server_urls or mcp_server_urls
        if not urls:
            raise ValueError("At least one server URL is required")

        # Clean and validate URLs
        self.server_urls = []
        for url in urls:
            if not url or not isinstance(url, str):
                raise ValueError(f"Invalid server URL: {url}")
            clean_url = url.rstrip('/')
            self.server_urls.append(clean_url)

        # Tool cache
        self._tools: List[Tool] = []

        # HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )

        logger.info(f"MCPClient initialized with {len(self.server_urls)} servers")

    async def discover_tools(self) -> List[Tool]:
        """Discover all available tools from MCP servers.

        Returns:
            List of Tool objects from all servers

        Raises:
            httpx.HTTPError: If all servers fail to respond
        """
        all_tools = []
        successful_discoveries = 0

        for server_url in self.server_urls:
            try:
                tools = await self._discover_tools_from_server(server_url)
                all_tools.extend(tools)
                successful_discoveries += 1
                logger.debug(f"Discovered {len(tools)} tools from {server_url}")

            except Exception as e:
                logger.warning(f"Failed to discover tools from {server_url}: {e}")

        if successful_discoveries == 0:
            raise httpx.HTTPError(f"Failed to discover tools from all {len(self.server_urls)} servers")

        # Cache discovered tools
        self._tools = all_tools
        logger.info(f"Discovered {len(all_tools)} total tools from {successful_discoveries} servers")
        return all_tools

    async def _discover_tools_from_server(self, server_url: str) -> List[Tool]:
        """Discover tools from a single MCP server.

        Args:
            server_url: URL of the MCP server

        Returns:
            List of Tool objects from this server

        Raises:
            httpx.HTTPError: If server request fails
            ValueError: If server response is invalid
        """
        # Try FastMCP endpoints
        endpoints_to_try = [
            "/mcp/tools",  # Standard MCP endpoint
            "/tools",      # Alternative endpoint
            "/v1/tools"    # Versioned endpoint
        ]

        for endpoint in endpoints_to_try:
            try:
                response = await self.client.get(f"{server_url}{endpoint}")
                response.raise_for_status()

                tools_data = response.json()
                return self._parse_tools_response(tools_data, server_url)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    continue  # Try next endpoint
                else:
                    logger.error(f"HTTP {e.response.status_code} from {server_url}{endpoint}")
                    raise
            except (httpx.RequestError, ValueError) as e:
                logger.warning(f"Request failed for {server_url}{endpoint}: {e}")
                continue

        raise httpx.HTTPError(f"No valid tool discovery endpoint found for {server_url}")

    def _parse_tools_response(self, tools_data: Any, server_url: str) -> List[Tool]:
        """Parse tools response from MCP server.

        Args:
            tools_data: JSON response from server
            server_url: URL of the server

        Returns:
            List of parsed Tool objects

        Raises:
            ValueError: If response format is invalid
        """
        tools = []

        if isinstance(tools_data, list):
            # Direct list of tools
            tools_list = tools_data
        elif isinstance(tools_data, dict):
            # Tools wrapped in object
            tools_list = tools_data.get("tools", [])
        else:
            raise ValueError(f"Invalid tools response format: {type(tools_data)}")

        for tool_data in tools_list:
            try:
                if not isinstance(tool_data, dict):
                    logger.warning(f"Skipping invalid tool data: {tool_data}")
                    continue

                tool = Tool(
                    name=tool_data.get("name", ""),
                    description=tool_data.get("description", ""),
                    parameters=tool_data.get("parameters", {}),
                    server_url=server_url
                )

                if not tool.name:
                    logger.warning(f"Skipping tool with empty name: {tool_data}")
                    continue

                tools.append(tool)

            except Exception as e:
                logger.warning(f"Failed to parse tool: {tool_data}, error: {e}")

        return tools

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """Execute a tool by name.

        Args:
            name: Tool name to execute
            args: Arguments to pass to the tool

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
            httpx.HTTPError: If tool execution fails
        """
        # Find tool by name
        tool = self._find_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found. Available tools: {[t.name for t in self._tools]}")

        return await self._execute_tool(tool, args)

    def _find_tool(self, name: str) -> Optional[Tool]:
        """Find a tool by name in the cached tools.

        Args:
            name: Tool name to find

        Returns:
            Tool object or None if not found
        """
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None

    async def _execute_tool(self, tool: Tool, args: Dict[str, Any]) -> Any:
        """Execute a specific tool.

        Args:
            tool: Tool object to execute
            args: Arguments to pass to the tool

        Returns:
            Tool execution result

        Raises:
            httpx.HTTPError: If execution fails
        """
        # Try different execution endpoints
        endpoints_to_try = [
            "/mcp/call",  # Standard MCP endpoint
            "/call",      # Alternative endpoint
            "/v1/call"    # Versioned endpoint
        ]

        payload = {
            "tool": tool.name,
            "arguments": args
        }

        for endpoint in endpoints_to_try:
            try:
                response = await self.client.post(
                    f"{tool.server_url}{endpoint}",
                    json=payload
                )
                response.raise_for_status()

                result_data = response.json()
                logger.debug(f"Tool {tool.name} executed successfully")

                # Extract result from response
                if isinstance(result_data, dict):
                    return result_data.get("result", result_data)
                else:
                    return result_data

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    continue  # Try next endpoint
                else:
                    logger.error(f"Tool execution failed: HTTP {e.response.status_code}")
                    raise
            except httpx.RequestError as e:
                logger.warning(f"Tool execution request failed: {e}")
                continue

        raise httpx.HTTPError(f"Failed to execute tool {tool.name} on {tool.server_url}")

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names.

        Returns:
            List of tool names
        """
        return [tool.name for tool in self._tools]

    def get_tools(self) -> List[Tool]:
        """Get list of discovered tools.

        Returns:
            List of Tool objects
        """
        return self._tools.copy()

    async def close(self):
        """Close HTTP client and cleanup resources."""
        try:
            await self.client.aclose()
            logger.debug("MCPClient closed successfully")
        except Exception as e:
            logger.warning(f"Error closing MCPClient: {e}")


# Backwards compatibility classes for tests

@dataclass
class MCPTool:
    """Backwards compatibility class for old tests."""
    name: str
    description: str
    parameters: Dict[str, Any] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class MCPToolset(MCPClient):
    """Backwards compatibility class for old tests."""

    def __init__(self, mcp_server_urls: List[str]):
        """Initialize with legacy parameter name."""
        super().__init__(mcp_server_urls=mcp_server_urls)

    async def get_tools(self) -> List[MCPTool]:
        """Get tools in legacy format."""
        tools = await super().get_tools()
        # Convert Tool dataclass to MCPTool for backwards compatibility
        return [
            MCPTool(name=tool.name, description=tool.description, parameters=tool.parameters)
            for tool in tools
        ]