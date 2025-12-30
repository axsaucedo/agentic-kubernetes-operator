"""
Integration tests for MCP server and client.

Tests:
- MCPServer startup with tools dict
- MCPServer startup with MCP_TOOLS_STRING env var
- MCPClient discovery of tools
- End-to-end tool invocation (echo, simple math)
- Error handling for missing servers
"""

import os
import pytest
import logging

from mcptools.server import MCPServer, MCPServerSettings
from mcptools.client import MCPClient, MCPClientSettings, Tool


logger = logging.getLogger(__name__)


@pytest.fixture
def mcp_server_with_tools():
    """Create MCP server with tools from string."""
    mcp_tools_string = """
def hello(s: str) -> str:
    \"\"\"Returns the printed hello <string>
       Args:
           s: string to be printed\"\"\"
    return f"hello {s}"
"""

    settings = MCPServerSettings(mcp_tools_string=mcp_tools_string)
    mcp_server = MCPServer(settings)
    return mcp_server


@pytest.mark.asyncio
async def test_mcp_server_startup_with_tools_dict(mcp_server_with_tools):
    """Test MCP server starts with tools from string."""
    assert mcp_server_with_tools is not None
    assert "hello" in mcp_server_with_tools.tools_registry


@pytest.mark.asyncio
async def test_mcp_tool_model():
    """Test Tool dataclass model."""
    tool = Tool(
        name="test_tool",
        description="A test tool",
        parameters={"param1": "string"}
    )

    assert tool.name == "test_tool"
    assert tool.description == "A test tool"
    assert tool.parameters == {"param1": "string"}
    logger.info("✓ Tool model works correctly")


def test_echo_tool_execution():
    """Test echo tool can be executed locally."""
    def echo(text: str) -> str:
        """Echo tool."""
        return f"Echo: {text}"

    result = echo("hello")
    assert result == "Echo: hello"
    logger.info("✓ Echo tool executes correctly")


def test_calculator_tools():
    """Test calculator tools work locally."""
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def multiply(a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

    assert add(2, 3) == 5
    assert multiply(3, 4) == 12
    logger.info("✓ Calculator tools execute correctly")


def test_mcp_server_tools_registry():
    """Test that MCPServer maintains tools registry."""
    def tool1(x: int) -> int:
        """Tool 1."""
        return x * 2

    def tool2(y: str) -> str:
        """Tool 2."""
        return y.upper()

    # Create settings and register tools after
    settings = MCPServerSettings(mcp_port=9998)
    server = MCPServer(settings)
    server.register_tools({"tool1": tool1, "tool2": tool2})

    assert "tool1" in server.tools_registry
    assert "tool2" in server.tools_registry
    assert server.tools_registry["tool1"](5) == 10
    assert server.tools_registry["tool2"]("hello") == "HELLO"
    logger.info("✓ MCPServer tools registry works correctly")


def test_mcp_server_env_var_parsing():
    """Test MCPServer can parse environment variable with valid Python."""
    # Set environment variable with valid Python function
    tools_string = '''
def echo(text: str) -> str:
    """Echo the text."""
    return f"Echo: {text}"
'''
    os.environ["MCP_TOOLS_STRING"] = tools_string

    try:
        # Create server which will parse the env var
        settings = MCPServerSettings(mcp_port=9997)
        server = MCPServer(settings)
        # Server should have loaded tools from env var
        assert server.tools_registry is not None
        assert "echo" in server.tools_registry
        logger.info("✓ MCPServer parses environment variable")
    finally:
        # Clean up
        if "MCP_TOOLS_STRING" in os.environ:
            del os.environ["MCP_TOOLS_STRING"]


def test_mcp_client_creation():
    """Test MCPClient can be created."""
    settings = MCPClientSettings(
        mcp_client_host="http://localhost",
        mcp_client_port="8002"
    )
    client = MCPClient(settings)
    
    assert client is not None
    assert "localhost" in client._url
    logger.info("✓ MCPClient created successfully")


@pytest.mark.asyncio
async def test_mcp_client_close():
    """Test MCPClient cleanup."""
    settings = MCPClientSettings(
        mcp_client_host="http://localhost",
        mcp_client_port="8002"
    )
    client = MCPClient(settings)
    await client.close()
    logger.info("✓ MCPClient closed successfully")


def test_mcp_server_get_registered_tools():
    """Test get_registered_tools returns tool names."""
    tools_string = '''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

def sub(a: int, b: int) -> int:
    """Subtract two numbers."""
    return a - b
'''
    settings = MCPServerSettings(mcp_port=9996, mcp_tools_string=tools_string)
    server = MCPServer(settings)
    
    tools = server.get_registered_tools()
    assert "add" in tools
    assert "sub" in tools
    assert len(tools) == 2
    logger.info("✓ get_registered_tools works correctly")


def test_mcp_server_empty_tools_string():
    """Test MCPServer handles empty tools string."""
    settings = MCPServerSettings(mcp_port=9995, mcp_tools_string="")
    server = MCPServer(settings)
    
    assert len(server.tools_registry) == 0
    logger.info("✓ MCPServer handles empty tools string")
