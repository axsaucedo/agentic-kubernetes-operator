#!/usr/bin/env python3
"""
Multi-Agent Coordination Example - Orchestrating agents via A2A communication.

This example demonstrates:
- Multiple agents running in separate processes
- Agent-to-Agent (A2A) communication via HTTP
- Coordinator delegating tasks to specialized agents
- Environment-based configuration for agent discovery
"""

import os
import asyncio
import logging
import subprocess
import time
from typing import Optional, List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AgentProcess:
    """Manages a single agent process."""

    def __init__(self, name: str, port: int, env_vars: Dict[str, str]):
        """Initialize agent process."""
        self.name = name
        self.port = port
        self.env_vars = env_vars
        self.process = None
        self.base_url = f"http://localhost:{port}"

    async def start(self) -> bool:
        """Start the agent process."""
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(self.env_vars)

            logger.info(f"Starting {self.name} agent on port {self.port}...")

            # Start agent server (from runtime/server/server.py)
            self.process = subprocess.Popen(
                ["python3", "-m", "runtime.server.server"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for server to be ready
            await self._wait_for_ready(timeout=10)
            logger.info(f"{self.name} agent started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start {self.name} agent: {e}")
            return False

    async def _wait_for_ready(self, timeout: int = 10) -> bool:
        """Wait for agent to be ready."""
        import httpx

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                async with httpx.AsyncClient(timeout=1.0) as client:
                    response = await client.get(f"{self.base_url}/ready")
                    if response.status_code == 200:
                        return True
            except Exception:
                pass
            await asyncio.sleep(0.5)

        logger.warning(f"{self.name} agent did not become ready within {timeout}s")
        return False

    async def stop(self) -> None:
        """Stop the agent process."""
        if self.process:
            logger.info(f"Stopping {self.name} agent...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            logger.info(f"{self.name} agent stopped")

    async def get_card(self) -> Optional[Dict]:
        """Get agent card for A2A communication."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/agent/card")
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.error(f"Failed to get card for {self.name}: {e}")
        return None

    async def invoke(self, task: str) -> Optional[str]:
        """Invoke the agent with a task."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/agent/invoke",
                    json={"task": task},
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("result")
        except Exception as e:
            logger.error(f"Failed to invoke {self.name}: {e}")
        return None


class MultiAgentOrchestrator:
    """Orchestrates multiple agents."""

    def __init__(self, env_file: str = ".env"):
        """Initialize orchestrator."""
        self.env_file = env_file
        self.agents: Dict[str, AgentProcess] = {}
        self._load_env()

    def _load_env(self) -> None:
        """Load environment configuration."""
        if os.path.exists(self.env_file):
            with open(self.env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        os.environ[key] = value

    async def setup_agents(self) -> bool:
        """Setup and start all agents."""
        logger.info("Setting up multi-agent system...")

        # Coordinator Agent
        coordinator_env = {
            "AGENT_NAME": os.getenv("COORDINATOR_NAME", "coordinator"),
            "AGENT_DESCRIPTION": os.getenv(
                "COORDINATOR_DESCRIPTION", "Coordinator agent"
            ),
            "AGENT_PORT": os.getenv("COORDINATOR_PORT", "8000"),
            "MODEL_API_URL": os.getenv("MODEL_API_URL"),
            "PEER_AGENTS": os.getenv("COORDINATOR_PEER_AGENTS", ""),
        }
        coordinator = AgentProcess(
            "coordinator",
            int(os.getenv("COORDINATOR_PORT", 8000)),
            coordinator_env,
        )
        self.agents["coordinator"] = coordinator

        # Researcher Agent
        researcher_env = {
            "AGENT_NAME": os.getenv("RESEARCHER_NAME", "researcher"),
            "AGENT_DESCRIPTION": os.getenv(
                "RESEARCHER_DESCRIPTION", "Researcher agent"
            ),
            "AGENT_PORT": os.getenv("RESEARCHER_PORT", "8001"),
            "MODEL_API_URL": os.getenv("MODEL_API_URL"),
            "PEER_AGENTS": os.getenv("RESEARCHER_PEER_AGENTS", ""),
        }
        researcher = AgentProcess(
            "researcher",
            int(os.getenv("RESEARCHER_PORT", 8001)),
            researcher_env,
        )
        self.agents["researcher"] = researcher

        # Analyst Agent (with math MCP tools)
        analyst_env = {
            "AGENT_NAME": os.getenv("ANALYST_NAME", "analyst"),
            "AGENT_DESCRIPTION": os.getenv("ANALYST_DESCRIPTION", "Analyst agent"),
            "AGENT_PORT": os.getenv("ANALYST_PORT", "8002"),
            "MODEL_API_URL": os.getenv("MODEL_API_URL"),
            "MCP_SERVERS": os.getenv("ANALYST_MCP_SERVERS", ""),
            "MCP_SERVER_MATH_TOOLS_URL": os.getenv(
                "ANALYST_MCP_SERVER_MATH_TOOLS_URL"
            ),
            "PEER_AGENTS": os.getenv("ANALYST_PEER_AGENTS", ""),
        }
        analyst = AgentProcess(
            "analyst",
            int(os.getenv("ANALYST_PORT", 8002)),
            analyst_env,
        )
        self.agents["analyst"] = analyst

        # Start all agents
        success = True
        for agent in self.agents.values():
            if not await agent.start():
                success = False

        if success:
            logger.info("All agents started successfully")
            await asyncio.sleep(1)  # Give agents time to settle

        return success

    async def run_coordination_test(self) -> None:
        """Run a test coordination task."""
        logger.info("Starting coordination test...")

        # Test 1: Coordinator delegates to analyst
        logger.info("Test 1: Coordinator delegating math task to analyst...")
        coordinator = self.agents["coordinator"]
        task = "Calculate: What is 123 + 456 - 78? Use the analyst agent to help."
        result = await coordinator.invoke(task)
        if result:
            logger.info(f"Coordinator result:\n{result}")
        else:
            logger.warning("Failed to get result from coordinator")

        await asyncio.sleep(2)

        # Test 2: Coordinator delegates to researcher
        logger.info("Test 2: Coordinator delegating research task to researcher...")
        task = "Research and summarize the capabilities of our agent system. Ask the researcher agent."
        result = await coordinator.invoke(task)
        if result:
            logger.info(f"Coordinator result:\n{result}")
        else:
            logger.warning("Failed to get result from coordinator")

    async def cleanup(self) -> None:
        """Stop all agents."""
        logger.info("Cleaning up agents...")
        for agent in self.agents.values():
            await agent.stop()

    async def run(self) -> None:
        """Run the multi-agent orchestration example."""
        try:
            if not await self.setup_agents():
                logger.error("Failed to setup agents")
                return

            await self.run_coordination_test()

        finally:
            await self.cleanup()


async def main():
    """Main entry point."""
    orchestrator = MultiAgentOrchestrator()
    await orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())
