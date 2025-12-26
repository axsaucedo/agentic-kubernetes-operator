#!/usr/bin/env python3
"""
Simple Math Agent - Local example for testing agent runtime.

This agent demonstrates:
- Loading configuration from environment variables
- Connecting to a local Ollama model API
- Using MCP tools (calculator via mcp-server-calculator)
- Reasoning with the language model
"""

import os
import asyncio
import logging
from typing import Optional

import httpx

# Configure logging
logging.basicConfig(
    level=os.getenv("AGENT_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleAgent:
    """Simple agent for mathematical reasoning."""

    def __init__(self):
        """Initialize agent from environment variables."""
        self.agent_name = os.getenv("AGENT_NAME", "math-agent")
        self.agent_description = os.getenv("AGENT_DESCRIPTION", "Math agent")
        self.agent_instructions = os.getenv("AGENT_INSTRUCTIONS", "")

        self.model_api_url = os.getenv("MODEL_API_URL", "http://localhost:11434/v1")
        self.model_api_key = os.getenv("MODEL_API_KEY", "ollama")

        # MCP configuration
        mcp_servers_str = os.getenv("MCP_SERVERS", "")
        self.mcp_servers = [s.strip() for s in mcp_servers_str.split(",") if s.strip()]

        self.mcp_endpoints = {}
        for mcp_name in self.mcp_servers:
            env_key = f"MCP_SERVER_{mcp_name.upper()}_URL"
            url = os.getenv(env_key, f"http://localhost:8001")
            self.mcp_endpoints[mcp_name] = url

        logger.info(f"Initialized agent: {self.agent_name}")
        logger.info(f"Model API URL: {self.model_api_url}")
        logger.info(f"MCP Servers: {self.mcp_servers}")

    async def get_mcp_tools(self) -> dict:
        """Fetch available tools from MCP servers."""
        tools = {}

        for mcp_name, endpoint in self.mcp_endpoints.items():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{endpoint}/tools")
                    if response.status_code == 200:
                        mcp_tools = response.json().get("tools", [])
                        logger.info(f"Loaded {len(mcp_tools)} tools from {mcp_name}")
                        tools[mcp_name] = mcp_tools
                    else:
                        logger.warning(f"Failed to fetch tools from {mcp_name}: {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching tools from {mcp_name}: {e}")

        return tools

    async def call_model(self, prompt: str) -> Optional[str]:
        """Call the language model with a prompt."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "model": "smollm2:135m",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 500,
                    "stream": False,
                }

                response = await client.post(
                    f"{self.model_api_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.model_api_key}"}
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    logger.info(f"Model response received ({len(content)} chars)")
                    return content
                else:
                    logger.error(f"Model API error: {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Error calling model: {e}")
            return None

    async def run_example(self) -> None:
        """Run example math reasoning task."""
        logger.info("Starting simple math agent example")
        logger.info(f"Agent: {self.agent_name}")
        logger.info(f"Description: {self.agent_description}")

        # Get available tools
        tools = await self.get_mcp_tools()

        # Prepare prompt with tool information
        tools_info = ""
        if tools:
            tools_info = "\n\nAvailable tools:\n"
            for mcp_name, tool_list in tools.items():
                tools_info += f"\n{mcp_name}:\n"
                for tool in tool_list:
                    tools_info += f"  - {tool.get('name', 'unknown')}: {tool.get('description', '')}\n"

        # Create reasoning prompt
        prompt = f"""You are a mathematical assistant.

{self.agent_instructions}

{tools_info}

Please solve this problem: What is 234 + 567 - 89?

Think through the calculation step by step."""

        logger.info("Sending prompt to model...")
        response = await self.call_model(prompt)

        if response:
            logger.info("Agent response:")
            print("\n" + "="*60)
            print(response)
            print("="*60 + "\n")
        else:
            logger.error("Failed to get response from model")


async def main():
    """Main entry point."""
    agent = SimpleAgent()
    await agent.run_example()


if __name__ == "__main__":
    asyncio.run(main())
