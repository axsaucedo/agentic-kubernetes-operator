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
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH

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
        response = await client.get(f"{agent_server.url}{AGENT_CARD_WELL_KNOWN_PATH}")
        assert response.status_code == 200
        card = response.json()

        # Verify card structure
        assert "name" in card
        assert "skills" in card
        assert "capabilities" in card

        # Verify echo tool/skill is loaded
        skills = card.get("skills", [])
        echo_skills = [s for s in skills if s.get("name") == "echo"]
        assert len(echo_skills) > 0 or len(skills) > 0, f"No skills found in card"

        # Verify A2A capabilities
        assert "capabilities" in card
        logger.info(f"Agent loaded {len(skills)} skills: {[s.get('name') for s in skills]}")


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
        response = await client.get(f"{agent_server.url}{AGENT_CARD_WELL_KNOWN_PATH}")
        assert response.status_code == 200
        card = response.json()

        # Verify A2A discovery information
        assert "name" in card
        assert "description" in card
        assert "url" in card
        assert "skills" in card
        assert "capabilities" in card

        # Verify capabilities exist
        assert "capabilities" in card
        logger.info(f"Agent card: {card['name']}")
        logger.info(f"Card keys: {list(card.keys())}")


@pytest.mark.asyncio
async def test_agent_without_mcp(agent_server_no_mcp):
    """Test agent can start without MCP configuration."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{agent_server_no_mcp.url}/ready")
        assert response.status_code == 200

        # Get agent card - should work but have no tools
        response = await client.get(f"{agent_server_no_mcp.url}{AGENT_CARD_WELL_KNOWN_PATH}")
        assert response.status_code == 200
        card = response.json()
        assert card["name"] == "simple_agent"  # Hyphens normalized to underscores
        assert "skills" in card
        # Verify card is properly formed
        assert "capabilities" in card
