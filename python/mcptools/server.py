"""
MCPServer for hosting tools via FastMCP protocol.

Clean, secure implementation without eval() usage.
Supports tool registration from environment variables safely.
"""

import json
import logging
from typing import Dict, Any, Callable, List, Optional
from fastmcp import FastMCP
import uvicorn

logger = logging.getLogger(__name__)


class MCPServer:
    """Secure MCP server that hosts tools via FastMCP protocol."""

    def __init__(self, port: int = None, tools: Dict[str, Callable] = None):
        """Initialize MCP server.

        Args:
            port: Port to run server on (default: 8002)
            tools: Dictionary of tool_name -> callable function
        """
        self.port = port or 8002
        self.mcp = FastMCP("Dynamic MCP Server")
        self.tools_registry: Dict[str, Callable] = {}

        # Register provided tools
        if tools:
            self.register_tools(tools)

        logger.info(f"MCPServer initialized on port {self.port} with {len(self.tools_registry)} tools")

    def register_tools(self, tools: Dict[str, Callable]):
        """Register multiple tools with the MCP server.

        Args:
            tools: Dictionary mapping tool names to callable functions
        """
        for name, func in tools.items():
            self.register_tool(name, func)

    def register_tool(self, name: str, func: Callable):
        """Register a single tool with the MCP server.

        Args:
            name: Tool name
            func: Callable function to register

        Raises:
            ValueError: If tool name is invalid or function is not callable
        """
        if not name or not isinstance(name, str):
            raise ValueError(f"Tool name must be a non-empty string, got: {name}")

        if not callable(func):
            raise ValueError(f"Tool function must be callable, got: {type(func)}")

        # Validate tool name (alphanumeric + underscore + hyphen)
        if not name.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f"Tool name '{name}' contains invalid characters")

        try:
            # Store reference
            self.tools_registry[name] = func

            # Register with FastMCP using function docstring and type hints
            self.mcp.tool(name)(func)
            logger.info(f"Registered tool: {name}")

        except Exception as e:
            logger.error(f"Failed to register tool {name}: {e}")
            # Remove from registry if registration failed
            self.tools_registry.pop(name, None)
            raise

    def register_tool_from_string(self, tools_string: str):
        """SECURE alternative to eval() for loading tools from environment.

        This method registers predefined tools based on a JSON configuration
        instead of executing arbitrary Python code.

        Args:
            tools_string: JSON string with tool configurations

        Example:
            '{"echo": {"type": "builtin"}, "calculator": {"type": "builtin"}}'
        """
        if not tools_string or not tools_string.strip():
            logger.info("No tools string provided")
            return

        try:
            # Parse as JSON (safe, no code execution)
            config = json.loads(tools_string)

            if not isinstance(config, dict):
                raise ValueError("Tools configuration must be a JSON object")

            # Register predefined tools based on configuration
            for tool_name, tool_config in config.items():
                self._register_predefined_tool(tool_name, tool_config)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in tools string: {e}")
            raise ValueError(f"Invalid JSON configuration: {e}")
        except Exception as e:
            logger.error(f"Failed to register tools from string: {e}")
            raise

    def _register_predefined_tool(self, name: str, config: Dict[str, Any]):
        """Register a predefined tool based on configuration.

        Args:
            name: Tool name
            config: Tool configuration dict

        Raises:
            ValueError: If tool type is not supported
        """
        tool_type = config.get("type")

        if tool_type == "builtin":
            # Register builtin tools
            builtin_tool = self._get_builtin_tool(name)
            if builtin_tool:
                self.register_tool(name, builtin_tool)
            else:
                logger.warning(f"Unknown builtin tool: {name}")

        else:
            raise ValueError(f"Unsupported tool type: {tool_type}")

    def _get_builtin_tool(self, name: str) -> Optional[Callable]:
        """Get a builtin tool function by name.

        Args:
            name: Tool name

        Returns:
            Tool function or None if not found
        """
        # Define safe, predefined tools
        builtin_tools = {
            "echo": lambda text: f"Echo: {text}",
            "calculator_add": lambda a, b: a + b,
            "calculator_subtract": lambda a, b: a - b,
            "calculator_multiply": lambda a, b: a * b,
            "calculator_divide": lambda a, b: a / b if b != 0 else "Error: Division by zero"
        }

        return builtin_tools.get(name)

    def get_registered_tools(self) -> List[str]:
        """Get list of registered tool names.

        Returns:
            List of tool names
        """
        return list(self.tools_registry.keys())

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
        logger.info(f"Starting MCP server on {host}:{self.port} with tools: {self.get_registered_tools()}")

        try:
            uvicorn.run(
                self.create_app(),
                host=host,
                port=self.port,
                log_level="info"
            )
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise


def create_echo_tool():
    """Create a simple echo tool for testing."""
    def echo_tool(text: str) -> str:
        """Echo the input text back to the user.

        Args:
            text: The text to echo

        Returns:
            The echoed text with prefix
        """
        return f"Echo: {text}"

    return echo_tool


def create_calculator_tools():
    """Create basic calculator tools for testing."""
    def add_numbers(a: float, b: float) -> float:
        """Add two numbers.

        Args:
            a: First number
            b: Second number

        Returns:
            Sum of the two numbers
        """
        return a + b

    def multiply_numbers(a: float, b: float) -> float:
        """Multiply two numbers.

        Args:
            a: First number
            b: Second number

        Returns:
            Product of the two numbers
        """
        return a * b

    return {
        "calculator_add": add_numbers,
        "calculator_multiply": multiply_numbers
    }


# Example usage (secure):
# MCP_TOOLS_STRING='{"echo": {"type": "builtin"}, "calculator_add": {"type": "builtin"}}'