"""Core agent functionality with local and remote agent implementations."""

import uuid
import logging
import httpx
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from modelapi.client import LiteLLM, ModelMessage
from agent.memory import LocalMemory, MemoryEvent

logger = logging.getLogger(__name__)


class AgentCard(BaseModel):
    """Agent discovery card for A2A protocol."""
    name: str
    description: str
    url: str
    skills: List[Dict[str, Any]] = []
    capabilities: List[str] = []


class RemoteAgent:
    """Wrapper for remote agent communication via A2A protocol."""

    def __init__(self, name: str, agent_card_url: str):
        """Initialize RemoteAgent.

        Args:
            name: Agent name
            agent_card_url: URL to fetch agent card from
        """
        self.name = name
        self.agent_card_url = agent_card_url
        self.agent_card: Optional[AgentCard] = None
        self._client = httpx.AsyncClient(timeout=30.0)
        logger.debug(f"RemoteAgent initialized: {name}")

    async def discover(self) -> AgentCard:
        """Discover agent capabilities via agent card.

        Returns:
            AgentCard with agent metadata

        Raises:
            Exception if discovery fails
        """
        try:
            response = await self._client.get(self.agent_card_url)
            response.raise_for_status()
            card_data = response.json()
            self.agent_card = AgentCard(**card_data)
            logger.info(f"Discovered agent {self.name}: {card_data.get('description', '')}")
            return self.agent_card
        except Exception as e:
            logger.error(f"Failed to discover agent {self.name}: {e}")
            raise

    async def invoke(self, task: str) -> str:
        """Invoke the remote agent with a task.

        Args:
            task: Task description to delegate

        Returns:
            Response from remote agent

        Raises:
            Exception if invocation fails
        """
        if not self.agent_card:
            await self.discover()

        # Extract base URL from agent card
        base_url = self.agent_card.url
        endpoint = f"{base_url}/agent/invoke"

        try:
            response = await self._client.post(
                endpoint,
                json={"task": task},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Remote agent {self.name} returned: {result}")
            return str(result.get("response", result))
        except Exception as e:
            logger.error(f"Failed to invoke agent {self.name}: {e}")
            raise

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
        logger.debug(f"RemoteAgent closed: {self.name}")


class Agent:
    """Main agent class that orchestrates LLM, tools, and sub-agents."""

    def __init__(
        self,
        name: str,
        description: str = "AI Agent",
        instructions: str = "You are a helpful assistant.",
        model_api: LiteLLM = None,
        tools: List[Any] = None,
        sub_agents: List[RemoteAgent] = None,
        memory: LocalMemory = None
    ):
        """Initialize Agent.

        Args:
            name: Agent name
            description: Agent description
            instructions: System instructions for the agent
            model_api: LiteLLM client for model access
            tools: List of tool providers (MCPToolset instances)
            sub_agents: List of RemoteAgent instances for delegation
            memory: LocalMemory instance for session tracking
        """
        self.name = name
        self.description = description
        self.instructions = instructions
        self.model_api = model_api
        self.tools = tools or []
        self.sub_agents = sub_agents or []
        self.memory = memory or LocalMemory()

        # Cache discovered tools
        self._available_tools: List[Dict[str, Any]] = []
        logger.info(f"Agent initialized: {name}")

    async def initialize(self):
        """Initialize agent by discovering tools and sub-agents."""
        logger.info(f"Initializing agent: {self.name}")

        # Discover MCP tools
        for toolset in self.tools:
            try:
                if hasattr(toolset, 'discover_tools'):
                    discovered_tools = await toolset.discover_tools()
                    if discovered_tools:
                        for tool in discovered_tools:
                            tool_dict = tool.model_dump() if hasattr(tool, 'model_dump') else dict(tool)
                            self._available_tools.append(tool_dict)
                        logger.info(f"Discovered {len(discovered_tools)} tools")
            except Exception as e:
                logger.warning(f"Failed to discover tools: {e}")

        # Discover sub-agents
        for sub_agent in self.sub_agents:
            try:
                await sub_agent.discover()
                logger.info(f"Discovered sub-agent: {sub_agent.name}")
            except Exception as e:
                logger.warning(f"Failed to discover sub-agent {sub_agent.name}: {e}")

        logger.info(f"Agent {self.name} initialization complete")

    async def process_message(
        self,
        message: str,
        session_id: str = None
    ) -> str:
        """Process a message and return response.

        Args:
            message: User message to process
            session_id: Session ID (created if not provided)

        Returns:
            Agent response
        """
        # Create session if needed
        if not session_id:
            session_id = await self.memory.create_session("agent", "user")

        logger.debug(f"Processing message for session {session_id}")

        # Log user message
        user_event = self.memory.create_event("user_message", message)
        await self.memory.add_event(session_id, user_event)

        # Build conversation context
        context = await self._build_context(session_id)

        # Generate LLM response
        try:
            messages = [
                ModelMessage(role="system", content=self.instructions),
                ModelMessage(role="user", content=context)
            ]

            response = await self.model_api.chat_completion(messages)

            # Log agent response
            response_event = self.memory.create_event(
                "agent_response",
                response.content,
                {"finish_reason": response.finish_reason}
            )
            await self.memory.add_event(session_id, response_event)

            logger.debug(f"Agent response: {response.content[:100]}...")
            return response.content
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            raise

    async def _build_context(self, session_id: str) -> str:
        """Build context from session history.

        Args:
            session_id: Session ID

        Returns:
            Formatted context for LLM prompt
        """
        events = await self.memory.get_session_events(session_id)

        context_parts = []

        # Add recent conversation history
        for event in events[-10:]:  # Last 10 events for context
            if event.event_type == "user_message":
                context_parts.append(f"User: {event.content}")
            elif event.event_type == "agent_response":
                context_parts.append(f"Assistant: {event.content}")

        # Add available tools information
        if self._available_tools:
            tools_info = "\n".join([
                f"- {tool.get('name', 'unknown')}: {tool.get('description', '')}"
                for tool in self._available_tools
            ])
            context_parts.append(f"Available tools:\n{tools_info}")

        # Add sub-agents information
        if self.sub_agents:
            agents_info = "\n".join([f"- {agent.name}" for agent in self.sub_agents])
            context_parts.append(f"Available sub-agents:\n{agents_info}")

        return "\n".join(context_parts)

    def get_agent_card(self, base_url: str) -> AgentCard:
        """Generate agent card for A2A discovery.

        Args:
            base_url: Base URL for the agent

        Returns:
            AgentCard with agent metadata
        """
        skills = []

        # Add MCP tools as skills
        for tool in self._available_tools:
            skills.append({
                "name": tool.get("name", "unknown"),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {})
            })

        # Add sub-agents as capabilities
        capabilities = ["task_execution"]
        if self.sub_agents:
            capabilities.append("agent_delegation")
        if self._available_tools:
            capabilities.append("tool_execution")

        return AgentCard(
            name=self.name,
            description=self.description,
            url=base_url,
            skills=skills,
            capabilities=capabilities
        )

    async def close(self):
        """Close all connections."""
        logger.info(f"Closing agent: {self.name}")

        if self.model_api:
            await self.model_api.close()

        for toolset in self.tools:
            if hasattr(toolset, 'close'):
                await toolset.close()

        for sub_agent in self.sub_agents:
            await sub_agent.close()

        logger.debug(f"Agent {self.name} closed")
