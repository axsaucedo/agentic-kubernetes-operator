"""
End-to-end integration tests for MCP server.

Tests the actual MCP server running with HTTP client communication.
Uses subprocess to start server and HTTP calls to test endpoints.
"""

import pytest
import httpx
import time
import logging
from multiprocessing import Process

from mcptools.server import MCPServer, MCPServerSettings
from mcptools.client import MCPClient, MCPClientSettings

logger = logging.getLogger(__name__)


def run_mcp_server(port: int, tools_string: str):
    """Run MCP server in a subprocess."""
    settings = MCPServerSettings(
        mcp_port=port,
        mcp_tools_string=tools_string,
        mcp_log_level="WARNING"
    )
    server = MCPServer(settings)
    server.run(transport="sse")


@pytest.fixture(scope="module")
def mcp_server_process():
    """Fixture that starts MCP server in subprocess."""
    port = 8050
    tools_string = '''
def echo(text: str) -> str:
    """Echo the input text back.
    Args:
        text: The text to echo
    """
    return f"Echo: {text}"

def add(a: int, b: int) -> int:
    """Add two numbers.
    Args:
        a: First number
        b: Second number
    """
    return a + b

def multiply(x: int, y: int) -> int:
    """Multiply two numbers.
    Args:
        x: First number
        y: Second number
    """
    return x * y
'''
    
    process = Process(target=run_mcp_server, args=(port, tools_string))
    process.start()
    
    # Wait for server to be ready
    ready = False
    for _ in range(30):
        try:
            response = httpx.get(f"http://localhost:{port}/health", timeout=1.0)
            if response.status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)
    
    if not ready:
        process.terminate()
        process.join(timeout=5)
        pytest.fail("MCP server did not start in time")
    
    yield {"url": f"http://localhost:{port}", "port": port}
    
    process.terminate()
    process.join(timeout=5)


class TestMCPServerHealthEndpoints:
    """Tests for MCP server health endpoints."""
    
    def test_health_endpoint(self, mcp_server_process):
        """Test /health endpoint returns correct response."""
        response = httpx.get(f"{mcp_server_process['url']}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "tools" in data
        assert data["tools"] >= 3  # echo, add, multiply
        logger.info("✓ Health endpoint works correctly")
    
    def test_ready_endpoint(self, mcp_server_process):
        """Test /ready endpoint returns registered tools."""
        response = httpx.get(f"{mcp_server_process['url']}/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "echo" in data["tools"]
        assert "add" in data["tools"]
        assert "multiply" in data["tools"]
        logger.info("✓ Ready endpoint works correctly")


class TestToolsFromString:
    """Tests for register_tools_from_string functionality."""
    
    def test_valid_tools_string_parsing(self):
        """Test that tools string is parsed correctly."""
        tools_string = '''
def square(x: int) -> int:
    """Square a number."""
    return x * x
'''
        settings = MCPServerSettings(
            mcp_port=8051,
            mcp_tools_string=tools_string
        )
        server = MCPServer(settings)
        
        assert "square" in server.tools_registry
        assert server.tools_registry["square"](5) == 25
        logger.info("✓ Tools from string parsed correctly")
    
    def test_empty_tools_string(self):
        """Test server handles empty tools string."""
        settings = MCPServerSettings(mcp_port=8052, mcp_tools_string="")
        server = MCPServer(settings)
        assert len(server.tools_registry) == 0
        logger.info("✓ Empty tools string handled correctly")
    
    def test_multiple_tools_in_string(self):
        """Test multiple tools can be defined in one string."""
        tools_string = '''
def tool_a(x: int) -> int:
    """Tool A."""
    return x + 1

def tool_b(x: int) -> int:
    """Tool B."""
    return x + 2

def tool_c(x: int) -> int:
    """Tool C."""
    return x + 3
'''
        settings = MCPServerSettings(mcp_port=8053, mcp_tools_string=tools_string)
        server = MCPServer(settings)
        
        assert len(server.tools_registry) == 3
        assert "tool_a" in server.tools_registry
        assert "tool_b" in server.tools_registry
        assert "tool_c" in server.tools_registry
        logger.info("✓ Multiple tools in string parsed correctly")
    
    def test_invalid_tools_string_raises_error(self):
        """Test that invalid Python in tools string raises error."""
        tools_string = "def invalid syntax here"
        settings = MCPServerSettings(mcp_port=8054, mcp_tools_string=tools_string)
        
        with pytest.raises(SyntaxError):
            MCPServer(settings)
        logger.info("✓ Invalid tools string raises SyntaxError")


class TestMCPServerToolRegistry:
    """Tests for MCP server tool registry."""
    
    def test_register_tools_programmatically(self):
        """Test tools can be registered programmatically."""
        def custom_tool(x: int) -> int:
            """Custom tool."""
            return x * 10
        
        settings = MCPServerSettings(mcp_port=8055)
        server = MCPServer(settings)
        server.register_tools({"custom_tool": custom_tool})
        
        assert "custom_tool" in server.tools_registry
        assert server.tools_registry["custom_tool"](5) == 50
        logger.info("✓ Programmatic tool registration works")
    
    def test_get_registered_tools(self):
        """Test get_registered_tools returns all tool names."""
        tools_string = '''
def t1() -> str:
    """Tool 1."""
    return "t1"

def t2() -> str:
    """Tool 2."""
    return "t2"
'''
        settings = MCPServerSettings(mcp_port=8056, mcp_tools_string=tools_string)
        server = MCPServer(settings)
        
        tools = server.get_registered_tools()
        assert len(tools) == 2
        assert "t1" in tools
        assert "t2" in tools
        logger.info("✓ get_registered_tools works correctly")
    
    def test_tool_with_various_types(self):
        """Test tools with different type annotations work."""
        tools_string = '''
def string_tool(s: str) -> str:
    """String tool."""
    return s.upper()

def int_tool(n: int) -> int:
    """Int tool."""
    return n * 2

def list_tool(items: list) -> int:
    """List tool."""
    return len(items)

def dict_tool(data: dict) -> str:
    """Dict tool."""
    return str(data)
'''
        settings = MCPServerSettings(mcp_port=8057, mcp_tools_string=tools_string)
        server = MCPServer(settings)
        
        assert server.tools_registry["string_tool"]("hello") == "HELLO"
        assert server.tools_registry["int_tool"](5) == 10
        assert server.tools_registry["list_tool"]([1, 2, 3]) == 3
        assert "test" in server.tools_registry["dict_tool"]({"test": 1})
        logger.info("✓ Tools with various types work correctly")


class TestMCPServerAppCreation:
    """Tests for MCP server app creation."""
    
    def test_create_app_returns_starlette_app(self):
        """Test create_app returns a valid Starlette app."""
        settings = MCPServerSettings(mcp_port=8058)
        server = MCPServer(settings)
        
        app = server.create_app(transport="sse")
        assert app is not None
        assert hasattr(app, "routes")
        logger.info("✓ create_app returns valid app")
    
    def test_create_app_with_different_transports(self):
        """Test create_app works with different transports."""
        settings = MCPServerSettings(mcp_port=8059)
        server = MCPServer(settings)
        
        # Test SSE transport
        app_sse = server.create_app(transport="sse")
        assert app_sse is not None
        
        # Test HTTP transport
        app_http = server.create_app(transport="http")
        assert app_http is not None
        
        logger.info("✓ create_app works with different transports")
