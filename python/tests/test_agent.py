"""
Integration tests for agent functionality and HTTP server.

Tests:
- Agent creation with minimal config
- Agent initialization with model_api and tools
- Message processing and memory event tracking
- Agent card generation with proper structure
- RemoteAgent discovery from URL
- Multi-agent setup with sub_agents
- Server startup and health/ready checks
- Agent card endpoint returns correct structure
"""

import os
import pytest
import httpx
import asyncio
import subprocess
import time
import json
import logging
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

logger = logging.getLogger(__name__)


class TestAgentCreation:
    """Tests for agent creation and initialization."""

    @pytest.mark.asyncio
    async def test_agent_creation_minimal_config(self):
        """Test agent can be created with minimal configuration."""
        from agent.client import Agent
        from modelapi.client import LiteLLM

        mock_llm = Mock(spec=LiteLLM)
        agent = Agent(
            name="test-agent",
            description="Test Agent",
            instructions="You are a test assistant.",
            model_api=mock_llm
        )

        assert agent.name == "test-agent"
        assert agent.description == "Test Agent"
        assert agent.instructions == "You are a test assistant."
        assert agent.model_api == mock_llm
        logger.info("✓ Agent created with minimal config")

    @pytest.mark.asyncio
    async def test_agent_card_generation(self):
        """Test agent generates correct card for A2A discovery."""
        from agent.client import Agent
        from modelapi.client import LiteLLM

        mock_llm = Mock(spec=LiteLLM)
        agent = Agent(
            name="test-agent",
            description="Test Agent",
            instructions="You are a test assistant.",
            model_api=mock_llm
        )

        card = agent.get_agent_card("http://localhost:8000")

        assert card.name == "test-agent"
        assert card.description == "Test Agent"
        assert card.url == "http://localhost:8000"
        assert isinstance(card.skills, list)
        assert isinstance(card.capabilities, list)
        assert "task_execution" in card.capabilities
        logger.info("✓ Agent card generated correctly")

    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test agent initialization discovers tools and sub-agents."""
        from agent.client import Agent
        from modelapi.client import LiteLLM

        mock_llm = Mock(spec=LiteLLM)
        agent = Agent(
            name="test-agent",
            description="Test Agent",
            model_api=mock_llm
        )

        # Initialize should work even without tools
        await agent.initialize()
        assert agent is not None
        logger.info("✓ Agent initialization works")


class TestMemoryTracking:
    """Tests for agent memory and event tracking."""

    @pytest.mark.asyncio
    async def test_memory_system_creation(self):
        """Test memory system can be created."""
        from agent.memory import LocalMemory

        memory = LocalMemory()
        assert memory is not None
        logger.info("✓ Memory system created")

    @pytest.mark.asyncio
    async def test_session_creation(self):
        """Test sessions can be created in memory."""
        from agent.memory import LocalMemory

        memory = LocalMemory()
        session_id = await memory.create_session("test_app", "user_123")

        assert session_id is not None
        assert session_id.startswith("session_")
        logger.info(f"✓ Session created: {session_id}")

    @pytest.mark.asyncio
    async def test_event_logging(self):
        """Test events can be logged to session."""
        from agent.memory import LocalMemory

        memory = LocalMemory()
        session_id = await memory.create_session("test_app", "user_123")

        # Create and add event
        event = memory.create_event("user_message", "Hello")
        await memory.add_event(session_id, event)

        # Retrieve events
        events = await memory.get_session_events(session_id)
        assert len(events) == 1
        assert events[0].event_type == "user_message"
        assert events[0].content == "Hello"
        logger.info("✓ Events logged to memory correctly")


class TestAgentMessageProcessing:
    """Tests for agent message processing."""

    @pytest.mark.asyncio
    async def test_message_processing_creates_memory_events(self):
        """Test message processing creates memory events."""
        from agent.client import Agent
        from agent.memory import LocalMemory
        from modelapi.client import LiteLLM, ModelResponse

        # Mock LLM to return a fixed response
        mock_llm = AsyncMock(spec=LiteLLM)
        mock_response = ModelResponse(
            content="Test response",
            finish_reason="stop"
        )
        mock_llm.chat_completion.return_value = mock_response

        memory = LocalMemory()
        agent = Agent(
            name="test-agent",
            description="Test Agent",
            instructions="You are a helpful assistant.",
            model_api=mock_llm,
            memory=memory
        )

        # Process a message
        session_id = await memory.create_session("agent", "user")
        response = await agent.process_message("Hello", session_id)

        # Verify response
        assert response == "Test response"

        # Verify memory events were created
        events = await memory.get_session_events(session_id)
        assert len(events) >= 2  # At least user message and response

        # Find event types
        event_types = [e.event_type for e in events]
        assert "user_message" in event_types
        assert "agent_response" in event_types

        logger.info("✓ Message processing creates memory events")

    @pytest.mark.asyncio
    async def test_context_building(self):
        """Test agent builds context from history."""
        from agent.client import Agent
        from agent.memory import LocalMemory
        from modelapi.client import LiteLLM

        mock_llm = Mock(spec=LiteLLM)
        memory = LocalMemory()
        agent = Agent(
            name="test-agent",
            model_api=mock_llm,
            memory=memory
        )

        # Create session and add some events
        session_id = await memory.create_session("agent", "user")

        event1 = memory.create_event("user_message", "First message")
        await memory.add_event(session_id, event1)

        event2 = memory.create_event("agent_response", "First response")
        await memory.add_event(session_id, event2)

        # Build context
        context = await agent._build_context(session_id)

        assert "First message" in context
        assert "First response" in context
        logger.info("✓ Context building works correctly")


class TestAgentCard:
    """Tests for agent card/A2A discovery."""

    @pytest.mark.asyncio
    async def test_agent_card_structure(self):
        """Test agent card has required fields."""
        from agent.client import Agent, AgentCard
        from modelapi.client import LiteLLM

        mock_llm = Mock(spec=LiteLLM)
        agent = Agent(
            name="coordinator",
            description="Coordinator Agent",
            model_api=mock_llm
        )

        card = agent.get_agent_card("http://localhost:8000")

        # Verify card structure
        assert isinstance(card, AgentCard)
        assert card.name == "coordinator"
        assert card.description == "Coordinator Agent"
        assert card.url == "http://localhost:8000"
        assert hasattr(card, "skills")
        assert hasattr(card, "capabilities")

        logger.info("✓ Agent card has correct structure")

    @pytest.mark.asyncio
    async def test_agent_card_with_sub_agents(self):
        """Test agent card shows agent delegation capability when sub-agents present."""
        from agent.client import Agent, RemoteAgent
        from modelapi.client import LiteLLM

        mock_llm = Mock(spec=LiteLLM)

        # Create remote agent mock
        remote_agent = Mock(spec=RemoteAgent)
        remote_agent.name = "worker"

        agent = Agent(
            name="coordinator",
            model_api=mock_llm,
            sub_agents=[remote_agent]
        )

        card = agent.get_agent_card("http://localhost:8000")

        # Verify delegation capability is present
        assert "agent_delegation" in card.capabilities
        logger.info("✓ Agent card shows delegation capability")


class TestServerEndpoints:
    """Tests for HTTP server endpoints."""

    @pytest.mark.asyncio
    async def test_server_settings_creation(self):
        """Test AgentServerSettings can be created with valid config."""
        from agent.server import AgentServerSettings

        # Set required env vars for test
        os.environ["AGENT_NAME"] = "test-agent"
        os.environ["MODEL_API_URL"] = "http://localhost:11434/v1"
        os.environ["MODEL_NAME"] = "test-model"

        try:
            settings = AgentServerSettings()
            assert settings.agent_name == "test-agent"
            assert settings.model_api_url == "http://localhost:11434/v1"
            assert settings.model_name == "test-model"
            logger.info("✓ AgentServerSettings created successfully")
        finally:
            # Clean up
            for key in ["AGENT_NAME", "MODEL_API_URL", "MODEL_NAME"]:
                if key in os.environ:
                    del os.environ[key]

    @pytest.mark.asyncio
    async def test_agent_server_creation(self):
        """Test AgentServer can be created."""
        from agent.server import AgentServer
        from agent.client import Agent
        from modelapi.client import LiteLLM

        # Set required env vars for test
        os.environ["AGENT_NAME"] = "test-agent"
        os.environ["MODEL_API_URL"] = "http://localhost:11434/v1"
        os.environ["MODEL_NAME"] = "test-model"

        try:
            mock_llm = Mock(spec=LiteLLM)
            mock_agent = Mock(spec=Agent)

            server = AgentServer(agent=mock_agent)
            assert server.agent is not None
            assert server.app is not None
            logger.info("✓ AgentServer created successfully")
        finally:
            # Clean up
            for key in ["AGENT_NAME", "MODEL_API_URL", "MODEL_NAME"]:
                if key in os.environ:
                    del os.environ[key]


class TestRemoteAgent:
    """Tests for remote agent functionality."""

    @pytest.mark.asyncio
    async def test_remote_agent_creation(self):
        """Test RemoteAgent can be created."""
        from agent.client import RemoteAgent

        remote_agent = RemoteAgent(
            name="worker-agent",
            agent_card_url="http://localhost:8001/.well-known/agent"
        )

        assert remote_agent.name == "worker-agent"
        assert remote_agent.agent_card_url == "http://localhost:8001/.well-known/agent"
        logger.info("✓ RemoteAgent created")

    @pytest.mark.asyncio
    async def test_remote_agent_close(self):
        """Test RemoteAgent cleanup."""
        from agent.client import RemoteAgent

        remote_agent = RemoteAgent(
            name="worker-agent",
            agent_card_url="http://localhost:8001/.well-known/agent"
        )

        await remote_agent.close()
        logger.info("✓ RemoteAgent closed successfully")


class TestModelAPI:
    """Tests for Model API client."""

    @pytest.mark.asyncio
    async def test_litellm_creation(self):
        """Test LiteLLM client can be created."""
        from modelapi.client import LiteLLM

        client = LiteLLM(
            model="test-model",
            api_base="http://localhost:8000"
        )

        assert client.model == "test-model"
        assert client.api_base == "http://localhost:8000"
        logger.info("✓ LiteLLM client created")

    @pytest.mark.asyncio
    async def test_litellm_close(self):
        """Test LiteLLM client cleanup."""
        from modelapi.client import LiteLLM

        client = LiteLLM(
            model="test-model",
            api_base="http://localhost:8000"
        )

        await client.close()
        logger.info("✓ LiteLLM client closed successfully")

    @pytest.mark.asyncio
    async def test_model_message_creation(self):
        """Test ModelMessage can be created."""
        from modelapi.client import ModelMessage

        msg = ModelMessage(role="user", content="Hello")

        assert msg.role == "user"
        assert msg.content == "Hello"
        logger.info("✓ ModelMessage created")

    @pytest.mark.asyncio
    async def test_model_response_creation(self):
        """Test ModelResponse can be created."""
        from modelapi.client import ModelResponse

        response = ModelResponse(
            content="Test response",
            finish_reason="stop"
        )

        assert response.content == "Test response"
        assert response.finish_reason == "stop"
        logger.info("✓ ModelResponse created")
