"""
Integration test for multi-agent coordination.

This test validates:
- Multiple agents can run simultaneously
- Agents discover each other via agent cards
- Agent cards are properly served for discovery
"""

import os
import subprocess
import time
import logging
from pathlib import Path
from typing import Dict, Optional

import pytest
import httpx

logger = logging.getLogger(__name__)


class MultiAgentCluster:
    """Manages multiple agent server subprocesses."""

    def __init__(self, agents_config: Dict[str, Dict[str, str]]):
        """Initialize multi-agent cluster manager.

        Args:
            agents_config: Dict of agent_name -> env_vars for each agent
        """
        self.agents_config = agents_config
        self.processes = {}
        self.urls = {}

    def start(self, timeout: int = 30) -> bool:
        """Start all configured agent servers.

        Args:
            timeout: Maximum seconds to wait for all servers to be ready

        Returns:
            True if all servers started successfully
        """
        logger.info(f"Starting {len(self.agents_config)} agent servers...")

        for agent_name, env_vars in self.agents_config.items():
            port = int(env_vars.get("AGENT_PORT", "8000"))
            self.urls[agent_name] = f"http://localhost:{port}"

            # Prepare environment
            env = os.environ.copy()
            env.update(env_vars)
            env["PYTHONUNBUFFERED"] = "1"

            # Find repo root directory (where agent/ package is located)
            repo_root = Path(__file__).parent.parent.parent

            try:
                process = subprocess.Popen(
                    ["python", "-m", "uvicorn", "agent.server:app",
                     "--host", "0.0.0.0", "--port", str(port)],
                    cwd=str(repo_root),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.processes[agent_name] = process
                logger.info(f"Started {agent_name} on port {port}")

            except Exception as e:
                logger.error(f"Failed to start agent {agent_name}: {e}")
                self.stop()
                return False

        # Wait for all servers to be ready
        if not self._wait_for_all_ready(timeout):
            logger.error("Not all servers became ready in time")
            self.stop()
            return False

        logger.info("All agent servers ready")
        return True

    def _wait_for_all_ready(self, timeout: int) -> bool:
        """Wait for all servers to be ready.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if all servers are ready
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            all_ready = True

            for agent_name, url in self.urls.items():
                try:
                    response = httpx.get(f"{url}/ready", timeout=1.0)
                    if response.status_code != 200:
                        all_ready = False
                except Exception:
                    all_ready = False

            if all_ready:
                return True

            time.sleep(0.5)

        return False

    def stop(self):
        """Stop all agent servers."""
        for agent_name, process in self.processes.items():
            logger.info(f"Stopping {agent_name}...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"{agent_name} didn't stop gracefully, killing...")
                process.kill()
            logger.info(f"{agent_name} stopped")

    def get_url(self, agent_name: str) -> str:
        """Get the URL for an agent."""
        return self.urls[agent_name]


@pytest.fixture
def multi_agent_cluster():
    """Fixture that provides multiple running agent servers."""
    # Configure three agents for multi-agent testing
    agents_config = {
        "coordinator": {
            "AGENT_NAME": "coordinator",
            "AGENT_DESCRIPTION": "Coordinator agent",
            "AGENT_PORT": "8011",
            "AGENT_INSTRUCTIONS": "You are the coordinator agent.",
            "MODEL_API_URL": os.getenv("MODEL_API_URL", "http://localhost:11434/v1"),
            "MODEL_NAME": os.getenv("MODEL_NAME", "smollm2:135m"),
            "AGENT_LOG_LEVEL": "INFO",
        },
        "worker-1": {
            "AGENT_NAME": "worker-1",
            "AGENT_DESCRIPTION": "First worker agent",
            "AGENT_PORT": "8012",
            "AGENT_INSTRUCTIONS": "You are worker agent 1.",
            "MODEL_API_URL": os.getenv("MODEL_API_URL", "http://localhost:11434/v1"),
            "MODEL_NAME": os.getenv("MODEL_NAME", "smollm2:135m"),
            "AGENT_LOG_LEVEL": "INFO",
        },
        "worker-2": {
            "AGENT_NAME": "worker-2",
            "AGENT_DESCRIPTION": "Second worker agent",
            "AGENT_PORT": "8013",
            "AGENT_INSTRUCTIONS": "You are worker agent 2.",
            "MODEL_API_URL": os.getenv("MODEL_API_URL", "http://localhost:11434/v1"),
            "MODEL_NAME": os.getenv("MODEL_NAME", "smollm2:135m"),
            "AGENT_LOG_LEVEL": "INFO",
        },
    }

    cluster = MultiAgentCluster(agents_config)
    if not cluster.start():
        raise RuntimeError("Failed to start multi-agent cluster")

    yield cluster
    cluster.stop()


@pytest.mark.asyncio
async def test_multi_agent_cluster_startup(multi_agent_cluster):
    """Test that all agents in the cluster start successfully."""
    async with httpx.AsyncClient() as client:
        for agent_name, url in multi_agent_cluster.urls.items():
            response = await client.get(f"{url}/ready")
            assert response.status_code == 200
            logger.info(f"{agent_name} is ready")


@pytest.mark.asyncio
async def test_multi_agent_discovery(multi_agent_cluster):
    """Test that agents can be discovered via agent cards."""
    async with httpx.AsyncClient() as client:
        for agent_name, url in multi_agent_cluster.urls.items():
            response = await client.get(f"{url}/agent/card")
            assert response.status_code == 200
            card = response.json()

            # Verify card has required fields for A2A discovery
            assert "name" in card
            assert "description" in card
            assert "endpoint" in card
            assert "capabilities" in card

            logger.info(f"Discovered {card['name']}: {card['description']}")


@pytest.mark.asyncio
async def test_multi_agent_health_endpoints(multi_agent_cluster):
    """Test that all agents report healthy status."""
    async with httpx.AsyncClient() as client:
        for agent_name, url in multi_agent_cluster.urls.items():
            response = await client.get(f"{url}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_multi_agent_card_consistency(multi_agent_cluster):
    """Test that agent cards provide consistent information."""
    async with httpx.AsyncClient() as client:
        cards = {}
        for agent_name, url in multi_agent_cluster.urls.items():
            response = await client.get(f"{url}/agent/card")
            assert response.status_code == 200
            cards[agent_name] = response.json()

        # Verify each card has the correct agent name
        for agent_name, card in cards.items():
            assert card["name"] == agent_name
            logger.info(f"Agent {agent_name} card validated")

        # Verify all agents have capabilities defined
        for agent_name, card in cards.items():
            capabilities = card.get("capabilities", {})
            assert "model_reasoning" in capabilities
            assert "tool_use" in capabilities
            assert "agent_to_agent" in capabilities
            logger.info(f"Agent {agent_name} capabilities: {capabilities}")
