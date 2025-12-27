"""
Agent Runtime Server Package

Provides the FastAPI-based agent runtime server with MCP tool integration
and Agent-to-Agent (A2A) communication.
"""

from agent.server.server import app  # noqa: F401
from agent.server.mcp_tools import MCPToolLoader, get_tool_loader  # noqa: F401
from agent.server.a2a import A2AClient, get_a2a_client  # noqa: F401

__all__ = [
    "app",
    "MCPToolLoader",
    "get_tool_loader",
    "A2AClient",
    "get_a2a_client",
]
