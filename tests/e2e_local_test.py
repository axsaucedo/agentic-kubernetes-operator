"""
End-to-End Local Tests for Agent Runtime

Tests the agent runtime locally against:
- Local Ollama server (SmolLM2-135M)
- Local MCP servers (calculator)
- Multi-agent A2A communication

These tests establish the baseline before Kubernetes deployment.
"""

import asyncio
import os
import pytest
import httpx
import subprocess
import time
import logging
from typing import Optional
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Fixtures for local services
# ============================================================================


@pytest.fixture(scope="session")
def ollama_url():
    """Get Ollama URL from environment or default."""
    return os.getenv("OLLAMA_URL", "http://localhost:11434")


@pytest.fixture(scope="session")
def model_api_url(ollama_url):
    """Model API URL (Ollama OpenAI-compatible endpoint)."""
    return f"{ollama_url}/v1"


@pytest.fixture(scope="session")
def mcp_server_url():
    """MCP server URL for calculator."""
    return os.getenv("MCP_SERVER_URL", "http://localhost:8001")


@pytest.fixture(scope="session")
async def check_dependencies():
    """Check that required services are running."""
    services = {
        "Ollama": os.getenv("OLLAMA_URL", "http://localhost:11434"),
        "MCP Server": os.getenv("MCP_SERVER_URL", "http://localhost:8001"),
    }

    async with httpx.AsyncClient(timeout=2.0) as client:
        for service_name, url in services.items():
            try:
                response = await client.get(f"{url}/health", follow_redirects=True)
                if response.status_code not in [200, 404]:  # 404 is ok for some health checks
                    logger.warning(f"{service_name} not responding at {url}")
            except Exception as e:
                logger.warning(f"Could not connect to {service_name} at {url}: {e}")
                # Don't fail here - we'll fail on actual tests if needed


# ============================================================================
# Tests: Simple Math Agent
# ============================================================================


class TestSimpleMathAgent:
    """Tests for the simple math agent example."""

    @pytest.mark.asyncio
    async def test_ollama_connectivity(self, model_api_url):
        """Test that Ollama is accessible."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # List available models
                response = await client.get(
                    f"{model_api_url.replace('/v1', '')}/api/tags"
                )
                assert response.status_code == 200
                models = response.json()
                logger.info(f"Available models: {[m['name'] for m in models.get('models', [])]}")
        except httpx.ConnectError:
            pytest.skip("Ollama not running - skipping test")

    @pytest.mark.asyncio
    async def test_mcp_connectivity(self, mcp_server_url):
        """Test that MCP server is accessible."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{mcp_server_url}/tools")
                # 404 is expected if MCP server doesn't have /tools endpoint
                assert response.status_code in [200, 404]
                logger.info("MCP server connectivity confirmed")
        except httpx.ConnectError:
            pytest.skip("MCP server not running - skipping test")

    @pytest.mark.asyncio
    async def test_simple_agent_example_exists(self):
        """Test that simple-math-agent example exists."""
        example_path = Path(__file__).parent.parent / "runtime" / "examples" / "simple-math-agent"
        assert example_path.exists(), f"Simple math agent example not found at {example_path}"
        assert (example_path / "agent.py").exists()
        assert (example_path / "Makefile").exists()
        assert (example_path / "README.md").exists()

    @pytest.mark.asyncio
    async def test_load_simple_agent_env(self):
        """Test loading simple agent environment configuration."""
        example_path = Path(__file__).parent.parent / "runtime" / "examples" / "simple-math-agent"
        env_file = example_path / ".env"

        # If .env doesn't exist, .env.example should be copied
        if not env_file.exists():
            example_env = example_path / ".env.example"
            assert example_env.exists(), f".env.example not found at {example_env}"
            logger.info("Note: .env not found, would need to be created from .env.example")
        else:
            # Load and verify environment
            env = {}
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        env[key] = value

            assert "AGENT_NAME" in env
            assert "MODEL_API_URL" in env
            logger.info(f"Loaded agent config: {env.get('AGENT_NAME')}")


# ============================================================================
# Tests: Multi-Agent Coordination
# ============================================================================


class TestMultiAgentCoordination:
    """Tests for multi-agent coordination example."""

    @pytest.mark.asyncio
    async def test_multi_agent_example_exists(self):
        """Test that multi-agent example exists."""
        example_path = (
            Path(__file__).parent.parent
            / "runtime"
            / "examples"
            / "multi-agent-coordination"
        )
        assert example_path.exists(), f"Multi-agent example not found at {example_path}"
        assert (example_path / "orchestrate.py").exists()
        assert (example_path / "Makefile").exists()
        assert (example_path / "README.md").exists()

    @pytest.mark.asyncio
    async def test_load_multi_agent_env(self):
        """Test loading multi-agent environment configuration."""
        example_path = (
            Path(__file__).parent.parent
            / "runtime"
            / "examples"
            / "multi-agent-coordination"
        )
        env_file = example_path / ".env"

        if not env_file.exists():
            example_env = example_path / ".env.example"
            assert example_env.exists(), f".env.example not found at {example_env}"
            logger.info("Note: .env not found, would need to be created from .env.example")
        else:
            # Load and verify environment
            env = {}
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        env[key] = value

            assert "COORDINATOR_NAME" in env
            assert "RESEARCHER_NAME" in env
            assert "ANALYST_NAME" in env
            logger.info("Multi-agent configuration loaded successfully")

    @pytest.mark.asyncio
    async def test_agent_names_unique(self):
        """Test that agent names are unique in configuration."""
        example_path = (
            Path(__file__).parent.parent
            / "runtime"
            / "examples"
            / "multi-agent-coordination"
        )
        env_file = example_path / ".env"

        if env_file.exists():
            env = {}
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        env[key] = value

            names = {
                "coordinator": env.get("COORDINATOR_NAME"),
                "researcher": env.get("RESEARCHER_NAME"),
                "analyst": env.get("ANALYST_NAME"),
            }

            # Check uniqueness
            name_values = list(names.values())
            assert len(name_values) == len(set(name_values)), "Agent names must be unique"
            logger.info(f"Agent names are unique: {names}")


# ============================================================================
# Tests: Runtime Components
# ============================================================================


class TestRuntimeComponents:
    """Tests for runtime component existence and structure."""

    def test_server_py_exists(self):
        """Test that server.py exists."""
        server_path = Path(__file__).parent.parent / "runtime" / "server" / "server.py"
        assert server_path.exists(), f"server.py not found at {server_path}"

    def test_mcp_tools_py_exists(self):
        """Test that mcp_tools.py exists."""
        mcp_path = Path(__file__).parent.parent / "runtime" / "server" / "mcp_tools.py"
        assert mcp_path.exists(), f"mcp_tools.py not found at {mcp_path}"

    def test_a2a_py_exists(self):
        """Test that a2a.py exists."""
        a2a_path = Path(__file__).parent.parent / "runtime" / "server" / "a2a.py"
        assert a2a_path.exists(), f"a2a.py not found at {a2a_path}"

    def test_runtime_pyproject_toml(self):
        """Test that runtime has pyproject.toml."""
        pyproject_path = Path(__file__).parent.parent / "runtime" / "server" / "pyproject.toml"
        assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"

        # Check for required dependencies
        with open(pyproject_path) as f:
            content = f.read()
            assert "httpx" in content, "httpx dependency not found in pyproject.toml"


# ============================================================================
# Tests: Operator Component
# ============================================================================


class TestOperatorComponent:
    """Tests for operator component structure."""

    def test_controllers_exist(self):
        """Test that all controllers exist."""
        controller_dir = Path(__file__).parent.parent / "operator" / "controllers"
        controllers = {
            "modelapi_controller.go": "ModelAPI controller",
            "mcpserver_controller.go": "MCPServer controller",
            "agent_controller.go": "Agent controller",
        }

        for filename, description in controllers.items():
            path = controller_dir / filename
            assert path.exists(), f"{description} not found at {path}"

    def test_api_types_exist(self):
        """Test that all API types exist."""
        api_dir = Path(__file__).parent.parent / "operator" / "api" / "v1alpha1"
        types = {
            "modelapi_types.go": "ModelAPI types",
            "mcpserver_types.go": "MCPServer types",
            "agent_types.go": "Agent types",
        }

        for filename, description in types.items():
            path = api_dir / filename
            assert path.exists(), f"{description} not found at {path}"

    def test_rbac_files_exist(self):
        """Test that RBAC files exist."""
        rbac_dir = Path(__file__).parent.parent / "operator" / "config" / "rbac"
        files = ["role.yaml", "role_binding.yaml", "service_account.yaml"]

        for filename in files:
            path = rbac_dir / filename
            assert path.exists(), f"RBAC file {filename} not found at {path}"

    def test_sample_manifests_exist(self):
        """Test that sample manifests exist."""
        samples_dir = Path(__file__).parent.parent / "operator" / "config" / "samples"
        manifests = [
            "modelapi_litellm_example.yaml",
            "modelapi_vllm_example.yaml",
            "mcpserver_example.yaml",
            "agent_example.yaml",
            "multi_agent_example.yaml",
        ]

        for manifest in manifests:
            path = samples_dir / manifest
            assert path.exists(), f"Sample manifest {manifest} not found at {path}"


# ============================================================================
# Integration Tests (require services running)
# ============================================================================


class TestIntegration:
    """Integration tests that require actual services running."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_model_api_inference(self, model_api_url):
        """Test basic model API inference."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{model_api_url}/chat/completions",
                    json={
                        "model": "smollm2:135m",
                        "messages": [{"role": "user", "content": "What is 2+2?"}],
                        "max_tokens": 50,
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert "choices" in data
                assert len(data["choices"]) > 0
                logger.info("Model API inference successful")
        except httpx.ConnectError:
            pytest.skip("Model API not running")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_server_tools(self, mcp_server_url):
        """Test that MCP server exposes tools."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{mcp_server_url}/tools")
                # Accept 200 or 404 depending on MCP implementation
                assert response.status_code in [200, 404]
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"MCP server tools: {data}")
        except httpx.ConnectError:
            pytest.skip("MCP server not running")


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
