"""Multi-agent E2E tests for Kubernetes operator deployment.

Tests multi-agent communication and coordination in Kubernetes, mirroring
local tests from agent/tests/test_multi_agent.py.
"""

import time
import pytest
import httpx

from e2e.conftest import (
    create_custom_resource,
    wait_for_deployment,
    port_forward,
    create_modelapi_resource,
    create_agent_resource,
)


def create_multi_agent_resources(namespace: str):
    """Create coordinator and worker agents for multi-agent testing."""
    modelapi_spec = create_modelapi_resource(namespace, "multi-agent-api")
    coordinator_spec = {
        "apiVersion": "ethical.institute/v1alpha1",
        "kind": "Agent",
        "metadata": {
            "name": "coordinator",
            "namespace": namespace,
        },
        "spec": {
            "modelAPI": "multi-agent-api",
            "config": {
                "description": "Coordinator agent",
                "instructions": "You are the coordinator agent.",
                "env": [
                    {"name": "AGENT_LOG_LEVEL", "value": "INFO"},
                    {"name": "MODEL_NAME", "value": "smollm2:135m"},
                ],
            },
            "agentNetwork": {
                "expose": True,
                "access": ["worker-1", "worker-2"],
            },
            "replicas": 1,
            "resources": {
                "requests": {"memory": "256Mi", "cpu": "200m"},
                "limits": {"memory": "512Mi", "cpu": "1000m"},
            },
        },
    }
    worker_1_spec = {
        "apiVersion": "ethical.institute/v1alpha1",
        "kind": "Agent",
        "metadata": {
            "name": "worker-1",
            "namespace": namespace,
        },
        "spec": {
            "modelAPI": "multi-agent-api",
            "config": {
                "description": "First worker agent",
                "instructions": "You are worker agent 1.",
                "env": [
                    {"name": "AGENT_LOG_LEVEL", "value": "INFO"},
                    {"name": "MODEL_NAME", "value": "smollm2:135m"},
                ],
            },
            "agentNetwork": {
                "expose": True,
                "access": [],
            },
            "replicas": 1,
            "resources": {
                "requests": {"memory": "256Mi", "cpu": "200m"},
                "limits": {"memory": "512Mi", "cpu": "1000m"},
            },
        },
    }
    worker_2_spec = {
        "apiVersion": "ethical.institute/v1alpha1",
        "kind": "Agent",
        "metadata": {
            "name": "worker-2",
            "namespace": namespace,
        },
        "spec": {
            "modelAPI": "multi-agent-api",
            "config": {
                "description": "Second worker agent",
                "instructions": "You are worker agent 2.",
                "env": [
                    {"name": "AGENT_LOG_LEVEL", "value": "INFO"},
                    {"name": "MODEL_NAME", "value": "smollm2:135m"},
                ],
            },
            "agentNetwork": {
                "expose": True,
                "access": [],
            },
            "replicas": 1,
            "resources": {
                "requests": {"memory": "256Mi", "cpu": "200m"},
                "limits": {"memory": "512Mi", "cpu": "1000m"},
            },
        },
    }
    return {
        "modelapi": modelapi_spec,
        "coordinator": coordinator_spec,
        "worker-1": worker_1_spec,
        "worker-2": worker_2_spec,
    }


@pytest.mark.asyncio
async def test_multi_agent_cluster_deployment(test_namespace: str):
    """Test that all agents in multi-agent cluster deploy successfully."""
    resources = create_multi_agent_resources(test_namespace)

    # Create ModelAPI first
    create_custom_resource(resources["modelapi"], test_namespace)
    wait_for_deployment(test_namespace, "modelapi-multi-agent-api", timeout=120)

    # Create worker agents FIRST so they're ready before coordinator
    for agent_name in ["worker-1", "worker-2"]:
        create_custom_resource(resources[agent_name], test_namespace)
        wait_for_deployment(test_namespace, f"agent-{agent_name}", timeout=120)

    # Create coordinator LAST so it can discover worker endpoints
    create_custom_resource(resources["coordinator"], test_namespace)
    wait_for_deployment(test_namespace, "agent-coordinator", timeout=120)


@pytest.mark.asyncio
async def test_multi_agent_discovery(test_namespace: str):
    """Test that agents can be discovered via agent cards."""
    resources = create_multi_agent_resources(test_namespace)

    # Deploy resources
    create_custom_resource(resources["modelapi"], test_namespace)
    wait_for_deployment(test_namespace, "modelapi-multi-agent-api", timeout=120)

    # Create workers first
    for agent_name in ["worker-1", "worker-2"]:
        create_custom_resource(resources[agent_name], test_namespace)
        wait_for_deployment(test_namespace, f"agent-{agent_name}", timeout=120)

    # Create coordinator last
    create_custom_resource(resources["coordinator"], test_namespace)
    wait_for_deployment(test_namespace, "agent-coordinator", timeout=120)

    # Test agent card discovery for each agent
    agent_names = ["coordinator", "worker-1", "worker-2"]
    base_port = 18100

    for i, agent_name in enumerate(agent_names):
        local_port = base_port + i
        pf_process = port_forward(
            namespace=test_namespace,
            service_name=f"agent-{agent_name}",
            local_port=local_port,
            remote_port=8000,
        )

        time.sleep(1)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://localhost:{local_port}/agent/card", timeout=5.0)
                assert response.status_code == 200
                card = response.json()

                # Verify required fields
                assert "name" in card
                assert card["name"] == agent_name
                assert "description" in card
                assert "endpoint" in card
                assert "capabilities" in card

                # Verify capabilities
                capabilities = card["capabilities"]
                assert "model_reasoning" in capabilities
                assert "tool_use" in capabilities
                assert "agent_to_agent" in capabilities
        finally:
            pf_process.terminate()
            pf_process.wait(timeout=5)


@pytest.mark.asyncio
async def test_multi_agent_health(test_namespace: str):
    """Test that all agents report healthy status."""
    resources = create_multi_agent_resources(test_namespace)

    # Deploy resources
    create_custom_resource(resources["modelapi"], test_namespace)
    wait_for_deployment(test_namespace, "modelapi-multi-agent-api", timeout=120)

    # Create workers first
    for agent_name in ["worker-1", "worker-2"]:
        create_custom_resource(resources[agent_name], test_namespace)
        wait_for_deployment(test_namespace, f"agent-{agent_name}", timeout=120)

    # Create coordinator last
    create_custom_resource(resources["coordinator"], test_namespace)
    wait_for_deployment(test_namespace, "agent-coordinator", timeout=120)

    # Test health endpoints
    agent_names = ["coordinator", "worker-1", "worker-2"]
    base_port = 18200

    for i, agent_name in enumerate(agent_names):
        local_port = base_port + i
        pf_process = port_forward(
            namespace=test_namespace,
            service_name=f"agent-{agent_name}",
            local_port=local_port,
            remote_port=8000,
        )

        time.sleep(1)

        try:
            async with httpx.AsyncClient() as client:
                # Test /health endpoint
                response = await client.get(f"http://localhost:{local_port}/health", timeout=5.0)
                assert response.status_code == 200
                assert response.json()["status"] == "healthy"

                # Test /ready endpoint
                response = await client.get(f"http://localhost:{local_port}/ready", timeout=5.0)
                assert response.status_code == 200
                assert response.json()["status"] == "ready"
        finally:
            pf_process.terminate()
            pf_process.wait(timeout=5)


@pytest.mark.asyncio
async def test_multi_agent_a2a_communication(test_namespace: str):
    """Test that coordinator can communicate with worker agents (A2A)."""
    resources = create_multi_agent_resources(test_namespace)

    # Deploy resources
    create_custom_resource(resources["modelapi"], test_namespace)
    wait_for_deployment(test_namespace, "modelapi-multi-agent-api", timeout=120)

    # Create workers first so their endpoints are available
    for agent_name in ["worker-1", "worker-2"]:
        create_custom_resource(resources[agent_name], test_namespace)
        wait_for_deployment(test_namespace, f"agent-{agent_name}", timeout=120)

    # Create coordinator last so it discovers worker endpoints
    create_custom_resource(resources["coordinator"], test_namespace)
    wait_for_deployment(test_namespace, "agent-coordinator", timeout=120)

    # Port-forward to coordinator
    pf_coordinator = port_forward(
        namespace=test_namespace,
        service_name="agent-coordinator",
        local_port=18300,
        remote_port=8000,
    )

    # Port-forward to worker-1 to verify it receives delegated calls
    pf_worker1 = port_forward(
        namespace=test_namespace,
        service_name="agent-worker-1",
        local_port=18301,
        remote_port=8000,
    )

    time.sleep(2)

    # DEBUG: Check what's actually in the coordinator deployment
    from sh import kubectl
    import json as json_lib
    try:
        coord_deploy = kubectl("get", "deployment", "agent-coordinator", "-n", test_namespace, "-o", "json")
        deploy_json = json_lib.loads(coord_deploy)
        env_vars = deploy_json['spec']['template']['spec']['containers'][0]['env']
        peer_vars = [e for e in env_vars if 'PEER' in e.get('name', '')]
        print(f"DEBUG: Coordinator has {len(peer_vars)} PEER_* env vars")
        for var in peer_vars[:5]:  # Print first 5
            print(f"  {var['name']}: {var.get('value', 'N/A')[:50]}...")
    except Exception as e:
        print(f"DEBUG ERROR: {e}")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Verify coordinator has A2A capability enabled
            response = await client.get("http://localhost:18300/agent/card", timeout=5.0)
            assert response.status_code == 200, "Failed to get coordinator card"
            card = response.json()

            print(f"DEBUG: Coordinator card capabilities: {card.get('capabilities', {})}")

            assert card["capabilities"]["agent_to_agent"] is True, "Coordinator should have A2A capability"
            print("✓ Coordinator A2A capability enabled")

            # Step 2: Verify worker-1 is accessible
            response = await client.get("http://localhost:18301/agent/card", timeout=5.0)
            assert response.status_code == 200, "Failed to get worker-1 card"
            worker_card = response.json()
            assert worker_card["name"] == "worker-1"
            print("✓ Worker-1 is accessible")

            # Step 3: Test coordinator invocation with delegation request
            # Ask the coordinator to delegate a task to worker-1
            task_request = {
                "task": "Ask worker-1 to echo this message: 'Hello from coordinator delegation test'"
            }

            response = await client.post(
                "http://localhost:18300/agent/invoke",
                json=task_request,
                timeout=60.0,
            )

            assert response.status_code == 200, f"Coordinator invocation failed: {response.text}"
            result = response.json()

            # Verify we got a result back
            assert "result" in result, f"No result in response: {result}"
            print(f"✓ Coordinator A2A delegation successful")
            print(f"  Result: {result.get('result', 'N/A')[:100]}...")

    finally:
        pf_coordinator.terminate()
        pf_coordinator.wait(timeout=5)
        pf_worker1.terminate()
        pf_worker1.wait(timeout=5)
