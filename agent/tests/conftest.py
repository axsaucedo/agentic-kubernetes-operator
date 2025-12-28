"""
Pytest configuration and fixtures for agent integration tests.

Provides fixtures for starting/stopping agent server instances and MCP servers.
"""

import os
import subprocess
import time
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import pytest
import httpx

logger = logging.getLogger(__name__)


class AgentServer:
    """Manages an agent server subprocess."""

    def __init__(self, port: int, env_vars: Dict[str, str]):
        """Initialize agent server manager.

        Args:
            port: Port to run server on
            env_vars: Environment variables to pass to server
        """
        self.port = port
        self.env_vars = env_vars
        self.process = None
        self.url = f"http://localhost:{port}"

    def start(self, timeout: int = 10) -> bool:
        """Start the server as a subprocess.

        Args:
            timeout: Maximum seconds to wait for server to be ready

        Returns:
            True if server started and became ready, False otherwise
        """
        logger.info(f"Starting agent server on port {self.port}...")

        # Prepare environment
        env = os.environ.copy()
        env.update(self.env_vars)
        env["PYTHONUNBUFFERED"] = "1"

        # Find repo root directory (where agent/ package is located)
        repo_root = Path(__file__).parent.parent

        try:
            self.process = subprocess.Popen(
                ["python", "-m", "uvicorn", "server.server:app",
                 "--host", "0.0.0.0", "--port", str(self.port)],
                cwd=str(repo_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for server to be ready
            if self._wait_for_readiness(timeout):
                logger.info(f"Agent server ready at {self.url}")
                return True
            else:
                logger.error(f"Server did not become ready within {timeout}s")
                self.stop()
                return False

        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise
            return False

    def _wait_for_readiness(self, timeout: int) -> bool:
        """Wait for server readiness endpoint to respond.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if server is ready, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = httpx.get(f"{self.url}/ready", timeout=1.0)
                if response.status_code == 200:
                    logger.info("Server readiness check passed")
                    return True
            except Exception:
                pass

            time.sleep(0.5)

        return False

    def stop(self):
        """Stop the server process."""
        if self.process:
            logger.info("Stopping agent server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Server didn't stop gracefully, killing...")
                self.process.kill()
            logger.info("Agent server stopped")

    def get_logs(self) -> str:
        """Get server logs for debugging."""
        if self.process:
            try:
                stdout, stderr = self.process.communicate(timeout=1)
                return f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
            except Exception:
                return "Could not retrieve logs"
        return "No logs available"


class MCPServer:
    """Manages test-mcp-echo-server subprocess."""

    def __init__(self, port: int = 8002):
        """Initialize MCP server manager.

        Args:
            port: Port to run server on
        """
        self.port = port
        self.process = None
        self.url = f"http://localhost:{port}"

    def start(self, timeout: int = 10) -> bool:
        """Start the MCP server as a subprocess.

        Args:
            timeout: Maximum seconds to wait for server to be ready

        Returns:
            True if server started and became ready
        """
        logger.info(f"Starting MCP echo server on port {self.port}...")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["MCP_SERVER_PORT"] = str(self.port)

        try:
            self.process = subprocess.Popen(
                ["test-mcp-echo-server"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for server to be ready
            if self._wait_for_readiness(timeout):
                logger.info(f"MCP server ready at {self.url}")
                return True
            else:
                logger.error(f"MCP server did not become ready within {timeout}s")
                self.stop()
                return False

        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            return False

    def _wait_for_readiness(self, timeout: int) -> bool:
        """Wait for MCP server to be ready.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if server is ready
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Try to get tools endpoint which should be available
                response = httpx.get(f"{self.url}/tools", timeout=1.0)
                if response.status_code in (200, 404):
                    # 200 if endpoint exists, 404 if MCP doesn't expose /tools
                    # but server is running
                    logger.info("MCP server responded")
                    return True
            except Exception:
                pass

            time.sleep(0.5)

        return False

    def stop(self):
        """Stop the MCP server."""
        if self.process:
            logger.info("Stopping MCP server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("MCP server didn't stop gracefully, killing...")
                self.process.kill()
            logger.info("MCP server stopped")


@pytest.fixture
def mcp_server():
    """Fixture that provides a started MCP echo server.

    Yields the server instance. Server is stopped after test completes.
    """
    server = MCPServer(port=8002)
    if not server.start():
        raise RuntimeError("Failed to start MCP server")
    yield server
    server.stop()


@pytest.fixture
def agent_server(mcp_server):
    """Fixture that provides a started agent server with MCP configured.

    Depends on mcp_server fixture to ensure MCP is available.
    Yields the server instance. Server is stopped after test completes.
    """
    server = None
    try:
        server = AgentServer(
            port=8001,
            env_vars={
                "AGENT_NAME": "test-agent",
                "AGENT_DESCRIPTION": "Test agent with MCP integration",
                "AGENT_INSTRUCTIONS": "You are a helpful test assistant with access to MCP tools.",
                "MODEL_API_URL": os.getenv("MODEL_API_URL", "http://localhost:11434/v1"),
                "MODEL_NAME": os.getenv("MODEL_NAME", "smollm2:135m"),
                "MCP_SERVERS": "echo_server",
                "MCP_SERVER_ECHO_SERVER_URL": mcp_server.url,
                "AGENT_LOG_LEVEL": "INFO",
            }
        )

        if not server.start():
            raise RuntimeError("Failed to start agent server")

        yield server
    finally:
        if server:
            server.stop()


@pytest.fixture
def agent_server_no_mcp():
    """Fixture that provides an agent server without MCP configuration.

    Useful for testing basic agent functionality without MCP tools.
    """
    server = None
    try:
        server = AgentServer(
            port=8003,
            env_vars={
                "AGENT_NAME": "simple-agent",
                "AGENT_DESCRIPTION": "Simple test agent without MCP",
                "AGENT_INSTRUCTIONS": "You are a helpful test assistant.",
                "MODEL_API_URL": os.getenv("MODEL_API_URL", "http://localhost:11434/v1"),
                "MODEL_NAME": os.getenv("MODEL_NAME", "smollm2:135m"),
                "AGENT_LOG_LEVEL": "INFO",
            }
        )

        if not server.start():
            raise RuntimeError("Failed to start agent server")

        yield server
    finally:
        if server:
            server.stop()
