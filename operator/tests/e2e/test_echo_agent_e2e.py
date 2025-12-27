"""End-to-end tests for Kubernetes operator deployment."""

import time
import subprocess
import pytest
import httpx

from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

from .conftest import (
    create_custom_resource,
    wait_for_deployment,
    port_forward,
    create_modelapi_resource,
    create_mcpserver_resource,
    create_agent_resource,
)


@pytest.mark.asyncio
async def test_echo_agent_full_deployment(test_namespace: str):
    """Test complete echo agent deployment."""
    modelapi_spec = create_modelapi_resource(test_namespace, "ollama-proxy")
    create_custom_resource(modelapi_spec, test_namespace)

    mcpserver_spec = create_mcpserver_resource(test_namespace, "echo-server")
    create_custom_resource(mcpserver_spec, test_namespace)

    agent_spec = create_agent_resource(
        namespace=test_namespace,
        modelapi_name="ollama-proxy",
        mcpserver_names=["echo-server"],
        agent_name="echo-agent",
    )
    create_custom_resource(agent_spec, test_namespace)

    wait_for_deployment(test_namespace, "modelapi-ollama-proxy", timeout=120)
    wait_for_deployment(test_namespace, "mcpserver-echo-server", timeout=120)
    wait_for_deployment(test_namespace, "agent-echo-agent", timeout=120)

    pf_process = port_forward(
        namespace=test_namespace,
        service_name="agent-echo-agent",
        local_port=18000,
        remote_port=8000,
    )

    time.sleep(2)
    agent_url = "http://localhost:18000"

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{agent_url}/ready", timeout=5.0)
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

        response = await client.get(f"{agent_url}/health", timeout=5.0)
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

        response = await client.get(f"{agent_url}/agent/card", timeout=5.0)
        assert response.status_code == 200
        card = response.json()
        assert "name" in card
        assert "tools" in card
        assert "capabilities" in card

    pf_process.terminate()
    pf_process.wait(timeout=5)


@pytest.mark.asyncio
async def test_echo_agent_invoke_task(test_namespace: str):
    """Test agent task invocation with model and MCP tools."""
    modelapi_spec = create_modelapi_resource(test_namespace, "ollama-proxy")
    create_custom_resource(modelapi_spec, test_namespace)

    mcpserver_spec = create_mcpserver_resource(test_namespace, "echo-server")
    create_custom_resource(mcpserver_spec, test_namespace)

    agent_spec = create_agent_resource(
        namespace=test_namespace,
        modelapi_name="ollama-proxy",
        mcpserver_names=["echo-server"],
        agent_name="echo-agent",
    )
    create_custom_resource(agent_spec, test_namespace)

    wait_for_deployment(test_namespace, "modelapi-ollama-proxy", timeout=120)
    wait_for_deployment(test_namespace, "mcpserver-echo-server", timeout=120)
    wait_for_deployment(test_namespace, "agent-echo-agent", timeout=120)

    pf_process = port_forward(
        namespace=test_namespace,
        service_name="agent-echo-agent",
        local_port=18001,
        remote_port=8000,
    )

    time.sleep(2)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "http://localhost:18001/agent/invoke",
            json={"task": "Use the echo tool to say 'Hello from Kubernetes!'"},
        )

        assert response.status_code == 200
        result = response.json()
        assert "result" in result

    pf_process.terminate()
    pf_process.wait(timeout=5)


@pytest.mark.asyncio
async def test_modelapi_deployment(test_namespace: str):
    """Test ModelAPI resource creation and deployment."""
    modelapi_spec = create_modelapi_resource(test_namespace, "test-modelapi")
    create_custom_resource(modelapi_spec, test_namespace)

    wait_for_deployment(test_namespace, "modelapi-test-modelapi", timeout=120)

    pf_process = port_forward(
        namespace=test_namespace,
        service_name="modelapi-test-modelapi",
        local_port=18010,
        remote_port=8000,
    )

    time.sleep(2)

    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:18010/models", timeout=5.0)
        assert response.status_code == 200

    pf_process.terminate()
    pf_process.wait(timeout=5)


@pytest.mark.asyncio
async def test_mcpserver_deployment(test_namespace: str):
    """Test MCPServer resource creation, deployment, and MCP functionality."""
    mcpserver_spec = create_mcpserver_resource(test_namespace, "test-mcp")
    create_custom_resource(mcpserver_spec, test_namespace)

    wait_for_deployment(test_namespace, "mcpserver-test-mcp", timeout=120)

    pf_process = port_forward(
        namespace=test_namespace,
        service_name="mcpserver-test-mcp",
        local_port=18020,
        remote_port=8000,
    )

    time.sleep(2)

    async with sse_client("http://localhost:18020/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            assert tools.tools
            tool_names = [t.name for t in tools.tools]
            assert "echo" in tool_names

            result = await session.call_tool("echo", {"text": "Hello from Kubernetes"})
            assert result.content
            assert result.content[0].text
            assert "Hello from Kubernetes" in result.content[0].text

    pf_process.terminate()
    pf_process.wait(timeout=5)
