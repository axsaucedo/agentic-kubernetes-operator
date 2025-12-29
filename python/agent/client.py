"""
Agent client implementation following Google ADK patterns.

Clean, simple implementation with proper streaming support and tool integration.
"""

import logging
from typing import List, Dict, Any, Optional, AsyncIterator
import httpx
from dataclasses import dataclass

from modelapi.client import ModelAPI
from agent.memory import LocalMemory, MemoryEvent
from mcptools.client import MCPClient

logger = logging.getLogger(__name__)


@dataclass
class AgentCard:
    """Agent discovery card for A2A protocol."""
    name: str
    description: str
    url: str
    skills: List[Dict[str, Any]]
    capabilities: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "skills": self.skills,
            "capabilities": self.capabilities
        }


class RemoteAgent:
    """Simple wrapper for remote agent communication via A2A protocol."""

    def __init__(self, name: str, card_url: str = None, agent_card_url: str = None):
        """Initialize RemoteAgent.

        Args:
            name: Agent name
            card_url: URL to fetch agent card from (.well-known/agent endpoint)
            agent_card_url: Legacy parameter name for card_url
        """
        # Handle legacy parameter
        url = card_url or agent_card_url
        if not url:
            raise ValueError("card_url (or agent_card_url) is required")
        self.name = name
        self.card_url = url.rstrip('/')
        self.agent_card: Optional[AgentCard] = None

        # HTTP client with reasonable timeout
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"RemoteAgent initialized: {name} -> {url}")

    async def discover(self) -> AgentCard:
        """Discover agent capabilities via agent card endpoint.

        Returns:
            AgentCard with agent metadata

        Raises:
            httpx.HTTPError: If discovery fails
        """
        try:
            response = await self.client.get(f"{self.card_url}/.well-known/agent")
            response.raise_for_status()

            card_data = response.json()
            self.agent_card = AgentCard(
                name=card_data.get("name", self.name),
                description=card_data.get("description", ""),
                url=card_data.get("url", self.card_url),
                skills=card_data.get("skills", []),
                capabilities=card_data.get("capabilities", [])
            )

            logger.info(f"Discovered remote agent: {self.name} - {self.agent_card.description}")
            return self.agent_card

        except httpx.HTTPError as e:
            logger.error(f"Failed to discover agent {self.name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error discovering agent {self.name}: {e}")
            raise

    async def invoke(self, task: str) -> str:
        """Invoke the remote agent with a task via A2A protocol.

        Args:
            task: Task description to delegate

        Returns:
            Response from remote agent

        Raises:
            ValueError: If agent not discovered
            httpx.HTTPError: If invocation fails
        """
        if not self.agent_card:
            await self.discover()

        try:
            response = await self.client.post(
                f"{self.agent_card.url}/agent/invoke",
                json={"task": task}
            )
            response.raise_for_status()

            result = response.json()
            response_text = result.get("response", str(result))

            logger.debug(f"Remote agent {self.name} completed task")
            return response_text

        except httpx.HTTPError as e:
            logger.error(f"Failed to invoke agent {self.name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error invoking agent {self.name}: {e}")
            raise

    async def close(self):
        """Close HTTP client and cleanup resources."""
        try:
            await self.client.aclose()
            logger.debug(f"RemoteAgent closed: {self.name}")
        except Exception as e:
            logger.warning(f"Error closing RemoteAgent {self.name}: {e}")


class Agent:
    """Simple Agent class following Google ADK patterns."""

    def __init__(
        self,
        name: str,
        instructions: str = None,
        model: ModelAPI = None,
        memory: Optional[LocalMemory] = None,
        # Legacy parameters for backwards compatibility
        description: str = None,
        model_api: ModelAPI = None,
        tools: List[Any] = None,
        sub_agents: List["RemoteAgent"] = None
    ):
        """Initialize Agent following Google ADK pattern.

        Args:
            name: Agent name
            instructions: System instructions (like Google ADK)
            model: ModelAPI client (like Google ADK model parameter)
            memory: Optional memory service (like Google ADK session service)
            description: Legacy parameter (ignored, kept for compatibility)
            model_api: Legacy parameter name for model
            tools: Legacy parameter (use add_tools() instead)
            sub_agents: Legacy parameter (use add_sub_agent() instead)
        """
        # Handle legacy parameters
        if model_api and not model:
            model = model_api
        if not instructions and description:
            instructions = description or "You are a helpful assistant."

        if not model:
            raise ValueError("model (or model_api) parameter is required")
        self.name = name
        self.instructions = instructions
        self.model = model
        self.memory = memory or LocalMemory()

        # Backwards compatibility attributes
        self.description = description or f"Agent: {name}"
        self.model_api = model  # Legacy alias

        # Tool and agent management
        self.tools: List[MCPClient] = []
        self.sub_agents: List[RemoteAgent] = []

        # Handle legacy sub_agents parameter
        if sub_agents:
            self.sub_agents.extend(sub_agents)

        logger.info(f"Agent initialized: {name}")

    async def initialize(self):
        """Legacy initialization method for backwards compatibility.

        In the new design, initialization is automatic in __init__.
        This method is kept for test compatibility.
        """
        # Already initialized in __init__, but this method satisfies the tests
        logger.debug(f"Agent {self.name} legacy initialize() called - already initialized")

    async def add_tools(self, tools: MCPClient):
        """Add tools to the agent.

        Args:
            tools: MCPClient for tool discovery and execution
        """
        self.tools.append(tools)
        # Discover tools immediately
        try:
            discovered = await tools.discover_tools()
            logger.info(f"Agent {self.name} added {len(discovered)} tools")
        except Exception as e:
            logger.warning(f"Failed to discover tools: {e}")

    async def add_sub_agent(self, sub_agent: RemoteAgent):
        """Add a sub-agent for delegation.

        Args:
            sub_agent: RemoteAgent instance
        """
        self.sub_agents.append(sub_agent)
        try:
            await sub_agent.discover()
            logger.info(f"Agent {self.name} added sub-agent: {sub_agent.name}")
        except Exception as e:
            logger.warning(f"Failed to discover sub-agent {sub_agent.name}: {e}")

    async def process_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        stream: bool = False
    ) -> AsyncIterator[str]:
        """Process a message and return response (streaming or non-streaming).

        Args:
            message: User message to process
            session_id: Optional session ID (created if not provided)
            stream: Whether to stream the response

        Yields:
            Content chunks (streaming) or single complete response (non-streaming)
        """
        # Create session if needed
        if not session_id:
            session_id = await self.memory.create_session("agent", "user", session_id)

        logger.debug(f"Processing message for session {session_id}, streaming={stream}")

        # Log user message
        user_event = self.memory.create_event("user_message", message)
        await self.memory.add_event(session_id, user_event)

        # Build conversation context from memory
        context = await self.memory.build_conversation_context(session_id)

        # Prepare messages for model
        messages = [{"role": "system", "content": self.instructions}]
        if context:
            messages.append({"role": "user", "content": context})
        messages.append({"role": "user", "content": message})

        try:
            if stream:
                # Streaming response
                response_chunks = []
                async for chunk in self.model.stream(messages):
                    response_chunks.append(chunk)
                    yield chunk

                # Log complete response
                complete_response = "".join(response_chunks)
                response_event = self.memory.create_event("agent_response", complete_response)
                await self.memory.add_event(session_id, response_event)

            else:
                # Non-streaming response
                response = await self.model.complete(messages)
                content = response["choices"][0]["message"]["content"]

                # Log response
                response_event = self.memory.create_event("agent_response", content)
                await self.memory.add_event(session_id, response_event)

                yield content

        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            logger.error(error_msg)

            # Log error event
            error_event = self.memory.create_event("error", error_msg)
            await self.memory.add_event(session_id, error_event)

            yield f"Sorry, I encountered an error: {str(e)}"

    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Execute a tool by name.

        Args:
            tool_name: Name of tool to execute
            args: Arguments for the tool

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
        """
        for tool_client in self.tools:
            try:
                return await tool_client.call_tool(tool_name, args)
            except ValueError:
                continue  # Try next tool client

        raise ValueError(f"Tool '{tool_name}' not found in any tool client")

    async def delegate_to_sub_agent(self, agent_name: str, task: str) -> str:
        """Delegate a task to a sub-agent.

        Args:
            agent_name: Name of sub-agent
            task: Task to delegate

        Returns:
            Response from sub-agent

        Raises:
            ValueError: If sub-agent not found
        """
        for sub_agent in self.sub_agents:
            if sub_agent.name == agent_name:
                return await sub_agent.invoke(task)

        raise ValueError(f"Sub-agent '{agent_name}' not found")

    def get_agent_card(self, base_url: str) -> AgentCard:
        """Generate agent card for A2A protocol discovery (sync for backwards compatibility).

        Args:
            base_url: Base URL where this agent is hosted

        Returns:
            AgentCard for this agent
        """
        # Collect available tools
        skills = []
        for tool_client in self.tools:
            tools = tool_client.get_tools()
            for tool in tools:
                skills.append({
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                })

        # Collect sub-agent capabilities
        capabilities = ["message_processing", "task_execution"]  # Basic capabilities
        if self.tools:
            capabilities.append("tool_execution")
        if self.sub_agents:
            capabilities.append("task_delegation")

        return AgentCard(
            name=self.name,
            description=self.description,  # Use the actual description
            url=base_url,
            skills=skills,
            capabilities=capabilities
        )

    async def close(self):
        """Close all connections and cleanup resources."""
        try:
            # Close model client
            if hasattr(self.model, 'close'):
                await self.model.close()

            # Close tool clients
            for tool_client in self.tools:
                if hasattr(tool_client, 'close'):
                    await tool_client.close()

            # Close sub-agents
            for sub_agent in self.sub_agents:
                await sub_agent.close()

            logger.debug(f"Agent {self.name} closed successfully")

        except Exception as e:
            logger.warning(f"Error closing Agent {self.name}: {e}")


# Simple message processing function for basic usage (like Google ADK example)
async def run_agent_once(agent: Agent, prompt: str, session_id: Optional[str] = None) -> str:
    """Simple function to run agent once and get complete response.

    Similar to Google ADK's run_agent_once pattern.

    Args:
        agent: Agent instance
        prompt: User prompt
        session_id: Optional session ID

    Returns:
        Complete agent response
    """
    response_chunks = []
    async for chunk in agent.process_message(prompt, session_id, stream=False):
        response_chunks.append(chunk)

    return "".join(response_chunks)