"""FastMCP server wrapper for tool hosting."""

import logging
from typing import Dict, Any, Callable, List, Optional
from fastmcp import FastMCP
from pydantic_settings import BaseSettings
import uvicorn

logger = logging.getLogger(__name__)


class MCPServerSettings(BaseSettings):
    """Settings for MCP server."""
    mcp_tools_string: str = ""  # Python literal string of tools
    mcp_server_port: int = 8002

    class Config:
        env_file = ".env"
        case_sensitive = False


class MCPServer:
    """Simple MCP server that can load tools from environment variables."""

    def __init__(self, port: int = None, tools: Dict[str, Callable] = None):
        """Initialize MCP server.

        Args:
            port: Port to run server on (default from settings)
            tools: Dictionary of tool_name -> callable function
        """
        settings = MCPServerSettings()
        self.port = port or settings.mcp_server_port
        self.mcp = FastMCP("Dynamic MCP Server")
        self.tools_registry: Dict[str, Callable] = {}

        if tools:
            self._register_tools(tools)
        elif settings.mcp_tools_string:
            self._load_tools_from_string(settings.mcp_tools_string)

    def _load_tools_from_string(self, tools_string: str):
        """Load tools from MCP_TOOLS_STRING environment variable.

        Args:
            tools_string: Python literal string representation of tools dict
        """
        try:
            tools_dict = eval(tools_string)  # Parse Python literal
            if isinstance(tools_dict, dict):
                self._register_tools(tools_dict)
            else:
                logger.error("MCP_TOOLS_STRING must be a dictionary literal")
        except Exception as e:
            logger.error(f"Failed to load tools from string: {e}")

    def _register_tools(self, tools: Dict[str, Callable]):
        """Register tools with FastMCP server.

        Args:
            tools: Dictionary mapping tool names to callable functions
        """
        for name, func in tools.items():
            if not callable(func):
                logger.warning(f"Skipping {name}: not callable")
                continue

            # Store reference
            self.tools_registry[name] = func

            # Use function docstring and type hints for MCP registration
            try:
                self.mcp.tool(name)(func)
                logger.info(f"Registered tool: {name}")
            except Exception as e:
                logger.error(f"Failed to register tool {name}: {e}")

    def create_app(self):
        """Create FastMCP ASGI app.

        Returns:
            ASGI application for FastMCP server
        """
        return self.mcp.create_app()

    def run(self, host: str = "0.0.0.0"):
        """Run the MCP server.

        Args:
            host: Host to bind to
        """
        logger.info(f"Starting MCP server on {host}:{self.port}")
        uvicorn.run(
            self.create_app(),
            host=host,
            port=self.port,
            log_level="info"
        )


# Example usage for environment-based tools:
# MCP_TOOLS_STRING='{"echo": lambda text: f"Echo: {text}", "add": lambda a, b: a + b}'
