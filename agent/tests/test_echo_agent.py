"""
Integration test for echo agent with MCP tool integration.

This test validates:
- Agent server starts with environment configuration
- Agent discovers tools from MCP server (test-mcp-echo-server)
- Agent card endpoint returns tool information
- Agent can access MCP tools
"""

import logging
import pytest
import httpx

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_echo_agent_server_startup(mcp_server, agent_server):
    """Test that echo agent server starts and becomes ready."""
    # Verify server is ready
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{agent_server.url}/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_echo_agent_loads_mcp_tools(mcp_server, agent_server):
    """Test that agent loads tools from MCP server."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{agent_server.url}/agent/card")
        assert response.status_code == 200
        card = response.json()

        # Verify card structure
        assert "name" in card
        assert "tools" in card
        assert "capabilities" in card

        # Verify echo tool is loaded
        tools = card["tools"]
        echo_tools = [t for t in tools if t.get("name") == "echo"]
        assert len(echo_tools) > 0, f"Echo tool not found. Available tools: {tools}"

        # Verify tool capabilities
        assert card["capabilities"]["tool_use"] is True
        logger.info(f"Agent loaded {len(tools)} tools: {[t.get('name') for t in tools]}")


@pytest.mark.asyncio
async def test_echo_agent_health_check(mcp_server, agent_server):
    """Test that agent health endpoint works."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{agent_server.url}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_echo_agent_card_endpoint(mcp_server, agent_server):
    """Test that agent card endpoint provides A2A discovery info."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{agent_server.url}/agent/card")
        assert response.status_code == 200
        card = response.json()

        # Verify A2A discovery information
        assert "name" in card
        assert "description" in card
        assert "endpoint" in card
        assert "tools" in card
        assert "capabilities" in card

        # Verify capabilities
        capabilities = card["capabilities"]
        assert "model_reasoning" in capabilities
        assert "tool_use" in capabilities
        assert "agent_to_agent" in capabilities

        logger.info(f"Agent card: {card['name']}")
        logger.info(f"Capabilities: {capabilities}")


@pytest.mark.asyncio
async def test_agent_without_mcp(agent_server_no_mcp):
    """Test agent can start without MCP configuration."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{agent_server_no_mcp.url}/ready")
        assert response.status_code == 200

        # Get agent card - should work but have no tools
        response = await client.get(f"{agent_server_no_mcp.url}/agent/card")
        assert response.status_code == 200
        card = response.json()
        assert card["name"] == "simple-agent"
        assert "tools" in card
        assert card["capabilities"]["tool_use"] is False
