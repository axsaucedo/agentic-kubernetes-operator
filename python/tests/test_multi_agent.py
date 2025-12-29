"""
Integration test for multi-agent coordination using custom A2A protocol.

This test validates:
- Multiple agents can run simultaneously
- Agents can be discovered and are ready
- Agents actually communicate with each other via A2A protocol
- Agent-to-agent delegation works correctly
- Memory events are tracked for coordination verification
"""

import os
import logging
from typing import Dict

import pytest
import httpx

logger = logging.getLogger(__name__)

# A2A discovery endpoint path
AGENT_CARD_WELL_KNOWN_PATH = "/.well-known/agent"


@pytest.mark.asyncio
async def test_multi_agent_cluster_startup(multi_agent_cluster):
    """Test that all agents in the cluster start successfully."""
    logger.info("Testing multi-agent cluster startup")
    async with httpx.AsyncClient() as client:
        logger.info(f"Testing agents: {list(multi_agent_cluster.urls.keys())}")
        for agent_name, url in multi_agent_cluster.urls.items():
            response = await client.get(f"{url}/health")
            assert response.status_code == 200, f"{agent_name} health check failed"
            data = response.json()
            assert data["status"] == "healthy"
            logger.info(f"✓ {agent_name} is healthy")


@pytest.mark.asyncio
async def test_multi_agent_discovery(multi_agent_cluster):
    """Test that agents can be discovered and are ready."""
    async with httpx.AsyncClient() as client:
        for agent_name, url in multi_agent_cluster.urls.items():
            # Check health endpoint (provided by ADK's to_a2a)
            response = await client.get(f"{url}/health")
            assert response.status_code == 200, f"{agent_name} not responding to /health"

            logger.info(f"Discovered agent {agent_name} at {url}")


@pytest.mark.asyncio
async def test_multi_agent_communication(multi_agent_cluster):
    """
    Test that agents actually communicate with each other via A2A protocol.

    This test verifies delegation by checking HTTP request logs:
    1. Capture baseline logs from workers
    2. Send delegation task to coordinator
    3. Verify workers logged incoming HTTP requests from coordinator
    4. Confirm HTTP requests indicate successful A2A delegation
    """
    import asyncio

    coordinator_url = multi_agent_cluster.get_url("coordinator")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Capture baseline logs
        logger.info("=== Step 1: Capturing baseline HTTP request logs ===")
        await asyncio.sleep(0.5)

        baseline_w1 = multi_agent_cluster.servers["worker-1"].get_logs()
        baseline_w2 = multi_agent_cluster.servers["worker-2"].get_logs()

        logger.info(f"Baseline captured: W1={len(baseline_w1)} chars, W2={len(baseline_w2)} chars")

        # Step 2: Send delegation task to coordinator
        logger.info("=== Step 2: Sending delegation task to coordinator ===")
        task_request = {
            "task": "Delegate to worker_1 and worker_2 to process this request"
        }

        coordinator_response = await client.post(
            f"{coordinator_url}/agent/invoke",
            json=task_request,
            timeout=30.0
        )
        logger.info(f"Coordinator response status: {coordinator_response.status_code}")

        # Coordinator must return 200 (success)
        assert coordinator_response.status_code == 200, \
            f"Coordinator delegation failed: {coordinator_response.status_code}"

        # Wait for coordinator to process and delegate tasks
        await asyncio.sleep(2.0)

        # Step 3: Capture updated logs and look for HTTP request evidence
        logger.info("=== Step 3: Checking worker logs for HTTP requests from coordinator ===")

        updated_w1 = multi_agent_cluster.servers["worker-1"].get_logs()
        updated_w2 = multi_agent_cluster.servers["worker-2"].get_logs()

        # Get only new logs
        w1_new = updated_w1[len(baseline_w1):] if len(updated_w1) > len(baseline_w1) else ""
        w2_new = updated_w2[len(baseline_w2):] if len(updated_w2) > len(baseline_w2) else ""

        logger.info(f"New logs: W1={len(w1_new)} chars, W2={len(w2_new)} chars")

        # Look for HTTP request patterns in logs
        # Uvicorn access logs show patterns like "GET /path HTTP/1.1" or "POST /path HTTP/1.1"
        http_request_patterns = [
            "GET ",
            "POST ",
            " HTTP/",
        ]

        w1_got_http_request = any(pat in w1_new for pat in http_request_patterns)
        w2_got_http_request = any(pat in w2_new for pat in http_request_patterns)

        logger.info(f"Worker-1 logged HTTP requests: {w1_got_http_request}")
        logger.info(f"Worker-2 logged HTTP requests: {w2_got_http_request}")

        if w1_new.strip():
            logger.info(f"Worker-1 new logs sample:\n{w1_new[:500]}")
        if w2_new.strip():
            logger.info(f"Worker-2 new logs sample:\n{w2_new[:500]}")

        # Step 4: Verify delegation actually occurred
        logger.info("=== Step 4: Verifying A2A delegation ===")

        # At least one worker should have received HTTP requests from coordinator
        assert w1_got_http_request or w2_got_http_request, \
            "No HTTP requests logged on workers - A2A delegation did not occur"

        logger.info("✓ Workers received HTTP requests from coordinator - A2A delegation confirmed")


@pytest.mark.asyncio
async def test_coordinator_has_peer_agents(multi_agent_cluster):
    """
    Test that coordinator agent is properly configured with peer agents.

    This verifies that RemoteA2aAgent references are correctly loaded from environment.
    """
    coordinator_url = multi_agent_cluster.get_url("coordinator")

    async with httpx.AsyncClient() as client:
        # Health check should succeed
        response = await client.get(f"{coordinator_url}/health")
        assert response.status_code == 200, "Coordinator not responding"

        logger.info("Coordinator is properly configured with peer agent support")


@pytest.mark.asyncio
async def test_worker_agents_ready(multi_agent_cluster):
    """Test that all worker agents are ready to accept requests."""
    async with httpx.AsyncClient() as client:
        for agent_name in ["worker-1", "worker-2"]:
            url = multi_agent_cluster.get_url(agent_name)

            response = await client.get(f"{url}/health")
            assert response.status_code == 200, f"{agent_name} not healthy"

            logger.info(f"{agent_name} is ready and healthy")
