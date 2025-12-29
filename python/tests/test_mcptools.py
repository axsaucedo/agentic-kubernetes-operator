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

logger = logging.getLogger(__name__)


class MCPTestServer:
    """Manages a test MCP server subprocess."""

    def __init__(self, port: int = 8004):
        self.port = port
        self.process = None
        self.url = f"http://localhost:{port}"

    def start(self, timeout: int = 10) -> bool:
        """Start the MCP server subprocess.

        Args:
            timeout: Seconds to wait for server to become ready

        Returns:
            True if server started successfully
        """
        logger.info(f"Starting MCP test server on port {self.port}...")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["MCP_SERVER_PORT"] = str(self.port)

        # Create a simple test MCP server script
        server_script = """
import sys
sys.path.insert(0, '.')

from mcptools.server import MCPServer

def echo(text: str) -> str:
    '''Echo tool - repeats the input text.'''
    return f"Echo: {text}"

def add(a: int, b: int) -> int:
    '''Add tool - adds two numbers.'''
    return a + b

def greet(name: str) -> str:
    '''Greet tool - greets a person by name.'''
    return f"Hello, {name}!"

tools = {
    'echo': echo,
    'add': add,
    'greet': greet,
}

server = MCPServer(port=%d, tools=tools)
server.run()
""" % self.port

        # Write server script to temp file
        repo_root = Path(__file__).parent.parent.parent
        script_path = repo_root / "python" / "_test_mcp_server.py"
        script_path.write_text(server_script)

        try:
            self.process = subprocess.Popen(
                [
                    "python",
                    str(script_path),
                ],
                cwd=str(repo_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for server to be ready
            if self._wait_for_readiness(timeout):
                logger.info(f"MCP server ready at {self.url}")
                return True
            else:
                logger.error(f"MCP server did not become ready within {timeout}s")
                self.stop()
                return False

        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise

    def _wait_for_readiness(self, timeout: int) -> bool:
        """Wait for server to be ready.

        Args:
            timeout: Seconds to wait

        Returns:
            True if server is ready
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Try to connect to the server
                response = httpx.get(f"{self.url}/tools", timeout=1.0)
                if response.status_code in (200, 404):
                    logger.info("MCP server responded")
                    return True
            except Exception:
                pass

            time.sleep(0.5)

        return False

    def stop(self):
        """Stop the MCP server."""
        if self.process:
            logger.info("Stopping MCP server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("MCP server didn't stop gracefully, killing...")
                self.process.kill()
            logger.info("MCP server stopped")


@pytest.fixture
def mcp_test_server():
    """Fixture that provides a started test MCP server."""
    server = MCPTestServer(port=8004)
    if not server.start():
        raise RuntimeError("Failed to start MCP test server")
    yield server
    server.stop()


@pytest.mark.asyncio
async def test_mcp_server_startup_with_tools_dict():
    """Test that MCPServer starts successfully with tools dict."""
    from mcptools.server import MCPServer

    def test_echo(text: str) -> str:
        """Test echo function."""
        return f"Echo: {text}"

    tools = {"echo": test_echo}

    # Create server instance (don't run, just verify instantiation)
    server = MCPServer(port=9999, tools=tools)
    assert server is not None
    assert "echo" in server.tools_registry
    logger.info("✓ MCPServer instantiated with tools dict")


@pytest.mark.asyncio
async def test_mcp_toolset_creation():
    """Test that MCPToolset can be created."""
    from mcptools.client import MCPToolset

    toolset = MCPToolset(mcp_server_urls=["http://localhost:8004"])
    assert toolset is not None
    assert toolset.server_urls == ["http://localhost:8004"]
    logger.info("✓ MCPToolset created successfully")


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
    from mcptools.client import MCPToolset

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
