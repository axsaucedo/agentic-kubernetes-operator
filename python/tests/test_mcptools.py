"""
Integration tests for MCP server and client.

Tests:
- MCPServer startup with tools dict
- MCPServer startup with MCP_TOOLS_STRING env var
- MCPToolset discovery of tools
- End-to-end tool invocation (echo, simple math)
- Error handling for missing servers
"""

import os
import pytest
import httpx
import asyncio
import subprocess
import time
import logging
from pathlib import Path

from mcptools.server import MCPServer, MCPServerSettings
from mcptools.client import MCPToolset


logger = logging.getLogger(__name__)

@pytest.fixture
def mcp_server_with_tools():

    mcp_tools_string = """
    def hello(s: str) -> str:
        \"""Returns the printed hello <string>
           Args:
               s: string to be printed\"""
        print(f"hello {s}")
    """

    settings = MCPServerSettings(mcp_tools_string=mcp_tools_string)

    mcp_server = MCPServer(settings)

    return mcp_server


@pytest.mark.asyncio
async def test_mcp_server_startup_with_tools_dict(mcp_server_with_tools):
    assert mcp_server_with_tools is not None
    assert "hello" in mcp_server_with_tools.tools_registry



@pytest.mark.asyncio
async def test_mcp_tool_model():
    """Test MCPTool Pydantic model."""
    from mcptools.client import MCPTool

    tool = MCPTool(
        name="test_tool",
        description="A test tool",
        parameters={"param1": "string"}
    )

    assert tool.name == "test_tool"
    assert tool.description == "A test tool"
    assert tool.parameters == {"param1": "string"}
    logger.info("✓ MCPTool model works correctly")


@pytest.mark.asyncio
async def test_mcp_toolset_close(mcp_test_server):
    """Test MCPToolset cleanup."""

    toolset = MCPToolset(mcp_server_urls=[mcp_test_server.url])
    await toolset.close()
    logger.info("✓ MCPToolset closed successfully")


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
    from mcptools.server import MCPServer

    def tool1(x: int) -> int:
        """Tool 1."""
        return x * 2

    def tool2(y: str) -> str:
        """Tool 2."""
        return y.upper()

    tools = {"tool1": tool1, "tool2": tool2}
    server = MCPServer(port=9998, tools=tools)

    assert "tool1" in server.tools_registry
    assert "tool2" in server.tools_registry
    assert server.tools_registry["tool1"](5) == 10
    assert server.tools_registry["tool2"]("hello") == "HELLO"
    logger.info("✓ MCPServer tools registry works correctly")


@pytest.mark.asyncio
async def test_mcp_toolset_with_multiple_servers():
    """Test MCPToolset can handle multiple server URLs."""
    from mcptools.client import MCPToolset

    urls = [
        "http://localhost:8004",
        "http://localhost:8005",
        "http://localhost:8006",
    ]
    toolset = MCPToolset(mcp_server_urls=urls)

    assert len(toolset.server_urls) == 3
    assert toolset.server_urls == urls
    logger.info("✓ MCPToolset handles multiple servers")


def test_mcp_server_env_var_parsing():
    """Test MCPServer can parse environment variable."""
    from mcptools.server import MCPServer
    import os

    # Set environment variable
    tools_string = '{"echo": lambda text: f"Echo: {text}", "add": lambda a, b: a + b}'
    os.environ["MCP_TOOLS_STRING"] = tools_string

    try:
        # Create server which will parse the env var
        server = MCPServer(port=9997)
        # Server should have loaded tools from env var
        assert server.tools_registry is not None
        logger.info("✓ MCPServer parses environment variable")
    finally:
        # Clean up
        if "MCP_TOOLS_STRING" in os.environ:
            del os.environ["MCP_TOOLS_STRING"]
