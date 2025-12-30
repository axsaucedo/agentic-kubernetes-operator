"""
End-to-end integration tests for agent delegation.

Tests the complete delegation flow where:
1. Coordinator agent receives a delegation request
2. Coordinator delegates to a worker agent
3. Worker processes the task
4. Both coordinator and worker memories are verified

Requires Ollama running locally with smollm2:135m model.
"""

import pytest
import httpx
import time
import logging
from multiprocessing import Process
from typing import List

from agent.server import AgentServerSettings, create_agent_server
from agent.client import RemoteAgent

logger = logging.getLogger(__name__)


def run_agent_server(
    port: int,
    model_url: str,
    model_name: str,
    agent_name: str,
    instructions: str,
    sub_agents_config: str = ""
):
    """Run agent server in subprocess with optional sub-agents."""
    settings = AgentServerSettings(
        agent_name=agent_name,
        agent_description=f"Agent: {agent_name}",
        agent_instructions=instructions,
        agent_port=port,
        model_api_url=model_url,
        model_name=model_name,
        agent_log_level="WARNING",
        agent_sub_agents=sub_agents_config
    )
    server = create_agent_server(settings)
    server.run()


@pytest.fixture(scope="module")
def ollama_available():
    """Check if Ollama is available."""
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def delegation_cluster(ollama_available):
    """Fixture that starts a coordinator with two worker agents."""
    if not ollama_available:
        pytest.skip("Ollama not available - skipping delegation tests")
    
    # Ollama base URL (without /v1 - ModelAPI adds it)
    model_url = "http://localhost:11434"
    model_name = "smollm2:135m"
    
    # Define agent configurations
    # Workers start first (no sub-agents)
    # Coordinator starts last (with sub-agents pointing to workers)
    agents = [
        {
            "name": "worker-1",
            "port": 8080,
            "instructions": "You are worker-1. Process tasks and always include 'WORKER-1-PROCESSED' in your response.",
            "sub_agents": ""
        },
        {
            "name": "worker-2",
            "port": 8081,
            "instructions": "You are worker-2. Process tasks and always include 'WORKER-2-PROCESSED' in your response.",
            "sub_agents": ""
        },
        {
            "name": "coordinator",
            "port": 8082,
            "instructions": "You are the coordinator. You manage worker-1 and worker-2.",
            "sub_agents": "worker-1:http://localhost:8080,worker-2:http://localhost:8081"
        }
    ]
    
    processes = []
    
    # Start workers first
    for agent in agents:
        if agent["name"] != "coordinator":
            p = Process(
                target=run_agent_server,
                args=(
                    agent["port"],
                    model_url,
                    model_name,
                    agent["name"],
                    agent["instructions"],
                    agent["sub_agents"]
                )
            )
            p.start()
            processes.append((agent["name"], p))
    
    # Wait for workers to be ready
    for agent in agents:
        if agent["name"] != "coordinator":
            ready = False
            for _ in range(60):
                try:
                    response = httpx.get(f"http://localhost:{agent['port']}/ready", timeout=2.0)
                    if response.status_code == 200:
                        ready = True
                        logger.info(f"Worker {agent['name']} ready on port {agent['port']}")
                        break
                except Exception:
                    pass
                time.sleep(0.5)
            
            if not ready:
                for _, p in processes:
                    p.terminate()
                    p.join(timeout=5)
                pytest.fail(f"Worker {agent['name']} did not start in time")
    
    # Now start coordinator
    coord_agent = next(a for a in agents if a["name"] == "coordinator")
    coord_process = Process(
        target=run_agent_server,
        args=(
            coord_agent["port"],
            model_url,
            model_name,
            coord_agent["name"],
            coord_agent["instructions"],
            coord_agent["sub_agents"]
        )
    )
    coord_process.start()
    processes.append(("coordinator", coord_process))
    
    # Wait for coordinator to be ready
    ready = False
    for _ in range(60):
        try:
            response = httpx.get(f"http://localhost:{coord_agent['port']}/ready", timeout=2.0)
            if response.status_code == 200:
                ready = True
                logger.info(f"Coordinator ready on port {coord_agent['port']}")
                break
        except Exception:
            pass
        time.sleep(0.5)
    
    if not ready:
        for _, p in processes:
            p.terminate()
            p.join(timeout=5)
        pytest.fail("Coordinator did not start in time")
    
    yield {
        "agents": agents,
        "urls": {a["name"]: f"http://localhost:{a['port']}" for a in agents}
    }
    
    for _, p in processes:
        p.terminate()
        p.join(timeout=5)


class TestDelegationEndpoint:
    """Tests for the /agent/delegate endpoint."""
    
    def test_delegate_endpoint_exists(self, delegation_cluster):
        """Test that /agent/delegate endpoint is available."""
        coord_url = delegation_cluster["urls"]["coordinator"]
        
        # Try to delegate (even if it fails, endpoint should exist)
        response = httpx.post(
            f"{coord_url}/agent/delegate",
            json={"agent": "worker-1", "task": "Test task"},
            timeout=60.0
        )
        
        # Should not be 404
        assert response.status_code != 404
        logger.info("✓ Delegate endpoint exists")
    
    def test_delegate_to_worker_1(self, delegation_cluster):
        """Test coordinator can delegate to worker-1."""
        coord_url = delegation_cluster["urls"]["coordinator"]
        
        response = httpx.post(
            f"{coord_url}/agent/delegate",
            json={"agent": "worker-1", "task": "Process this data item"},
            timeout=60.0
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["agent"] == "worker-1"
        assert len(data["response"]) > 0
        
        logger.info(f"✓ Delegated to worker-1: {data['response'][:50]}...")
    
    def test_delegate_to_worker_2(self, delegation_cluster):
        """Test coordinator can delegate to worker-2."""
        coord_url = delegation_cluster["urls"]["coordinator"]
        
        response = httpx.post(
            f"{coord_url}/agent/delegate",
            json={"agent": "worker-2", "task": "Analyze this dataset"},
            timeout=60.0
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["agent"] == "worker-2"
        assert len(data["response"]) > 0
        
        logger.info(f"✓ Delegated to worker-2: {data['response'][:50]}...")
    
    def test_delegate_to_nonexistent_agent(self, delegation_cluster):
        """Test delegation to non-existent agent returns 404."""
        coord_url = delegation_cluster["urls"]["coordinator"]
        
        response = httpx.post(
            f"{coord_url}/agent/delegate",
            json={"agent": "nonexistent-agent", "task": "Some task"},
            timeout=30.0
        )
        
        assert response.status_code == 404
        logger.info("✓ Non-existent agent returns 404")


class TestMemoryEndpoints:
    """Tests for memory inspection endpoints."""
    
    def test_memory_events_endpoint_exists(self, delegation_cluster):
        """Test /memory/events endpoint is available."""
        for name, url in delegation_cluster["urls"].items():
            response = httpx.get(f"{url}/memory/events")
            assert response.status_code == 200
            data = response.json()
            assert "events" in data
            assert "agent" in data
            assert data["agent"] == name
        
        logger.info("✓ Memory events endpoint works for all agents")
    
    def test_memory_sessions_endpoint_exists(self, delegation_cluster):
        """Test /memory/sessions endpoint is available."""
        for name, url in delegation_cluster["urls"].items():
            response = httpx.get(f"{url}/memory/sessions")
            assert response.status_code == 200
            data = response.json()
            assert "sessions" in data
            assert "agent" in data
        
        logger.info("✓ Memory sessions endpoint works for all agents")


class TestDelegationMemoryTracking:
    """Tests for verifying delegation is tracked in memory."""
    
    def test_coordinator_logs_delegation_events(self, delegation_cluster):
        """Test coordinator memory contains delegation_request and delegation_response."""
        coord_url = delegation_cluster["urls"]["coordinator"]
        
        # Perform a delegation
        delegate_response = httpx.post(
            f"{coord_url}/agent/delegate",
            json={"agent": "worker-1", "task": "Test delegation tracking"},
            timeout=60.0
        )
        assert delegate_response.status_code == 200
        
        # Check coordinator memory
        memory_response = httpx.get(f"{coord_url}/memory/events")
        assert memory_response.status_code == 200
        
        events = memory_response.json()["events"]
        
        # Find delegation events
        delegation_requests = [e for e in events if e["event_type"] == "delegation_request"]
        delegation_responses = [e for e in events if e["event_type"] == "delegation_response"]
        
        assert len(delegation_requests) >= 1, "Should have at least one delegation_request event"
        assert len(delegation_responses) >= 1, "Should have at least one delegation_response event"
        
        # Verify delegation request content
        last_request = delegation_requests[-1]
        assert "worker-1" in str(last_request["content"])
        assert "Test delegation tracking" in str(last_request["content"])
        
        logger.info("✓ Coordinator memory contains delegation events")
    
    def test_worker_logs_task_events(self, delegation_cluster):
        """Test worker memory contains user_message and agent_response from delegation."""
        coord_url = delegation_cluster["urls"]["coordinator"]
        worker_url = delegation_cluster["urls"]["worker-1"]
        
        # Clear worker memory by noting current event count
        initial_memory = httpx.get(f"{worker_url}/memory/events").json()
        initial_count = len(initial_memory["events"])
        
        # Perform a delegation
        unique_task = f"UNIQUE_TASK_{time.time()}"
        delegate_response = httpx.post(
            f"{coord_url}/agent/delegate",
            json={"agent": "worker-1", "task": unique_task},
            timeout=60.0
        )
        assert delegate_response.status_code == 200
        
        # Check worker memory
        memory_response = httpx.get(f"{worker_url}/memory/events")
        events = memory_response.json()["events"]
        
        # New events should be added
        new_events = events[initial_count:]
        
        user_messages = [e for e in new_events if e["event_type"] == "user_message"]
        agent_responses = [e for e in new_events if e["event_type"] == "agent_response"]
        
        assert len(user_messages) >= 1, "Worker should have received user_message"
        assert len(agent_responses) >= 1, "Worker should have generated agent_response"
        
        # Verify the task content
        task_found = any(unique_task in str(e["content"]) for e in user_messages)
        assert task_found, f"Worker should have received the task: {unique_task}"
        
        logger.info("✓ Worker memory contains task events from delegation")


class TestEndToEndDelegationFlow:
    """Complete end-to-end tests for multi-agent delegation."""
    
    def test_full_delegation_flow_to_worker_1(self, delegation_cluster):
        """Test complete delegation flow and verify both memories."""
        coord_url = delegation_cluster["urls"]["coordinator"]
        worker_url = delegation_cluster["urls"]["worker-1"]
        
        # Unique task identifier
        task_id = f"E2E_TEST_{int(time.time())}"
        task = f"Process item with ID {task_id}"
        
        # 1. Delegate from coordinator to worker-1
        delegate_response = httpx.post(
            f"{coord_url}/agent/delegate",
            json={"agent": "worker-1", "task": task},
            timeout=60.0
        )
        
        assert delegate_response.status_code == 200
        result = delegate_response.json()
        assert result["status"] == "completed"
        
        # 2. Verify coordinator memory
        coord_memory = httpx.get(f"{coord_url}/memory/events").json()
        coord_events = coord_memory["events"]
        
        # Should have delegation_request
        delegation_requests = [e for e in coord_events if e["event_type"] == "delegation_request"]
        assert len(delegation_requests) >= 1
        
        # Should contain task_id
        found_in_coordinator = any(
            task_id in str(e["content"]) 
            for e in delegation_requests
        )
        assert found_in_coordinator, "Coordinator should have logged the delegation request"
        
        # Should have delegation_response
        delegation_responses = [e for e in coord_events if e["event_type"] == "delegation_response"]
        assert len(delegation_responses) >= 1
        
        # 3. Verify worker memory
        worker_memory = httpx.get(f"{worker_url}/memory/events").json()
        worker_events = worker_memory["events"]
        
        # Should have user_message with the task
        user_messages = [e for e in worker_events if e["event_type"] == "user_message"]
        found_in_worker = any(
            task_id in str(e["content"]) 
            for e in user_messages
        )
        assert found_in_worker, "Worker should have received the task"
        
        # Should have agent_response
        agent_responses = [e for e in worker_events if e["event_type"] == "agent_response"]
        assert len(agent_responses) >= 1
        
        logger.info("✓ Full delegation flow verified with memory tracking")
    
    def test_delegation_to_both_workers(self, delegation_cluster):
        """Test delegating to both workers and verify both process tasks."""
        coord_url = delegation_cluster["urls"]["coordinator"]
        worker1_url = delegation_cluster["urls"]["worker-1"]
        worker2_url = delegation_cluster["urls"]["worker-2"]
        
        # Unique tasks
        task1_id = f"W1_TASK_{int(time.time())}"
        task2_id = f"W2_TASK_{int(time.time())}"
        
        # Delegate to worker-1
        resp1 = httpx.post(
            f"{coord_url}/agent/delegate",
            json={"agent": "worker-1", "task": f"Task {task1_id} for worker-1"},
            timeout=60.0
        )
        assert resp1.status_code == 200
        
        # Delegate to worker-2
        resp2 = httpx.post(
            f"{coord_url}/agent/delegate",
            json={"agent": "worker-2", "task": f"Task {task2_id} for worker-2"},
            timeout=60.0
        )
        assert resp2.status_code == 200
        
        # Verify worker-1 received its task
        w1_memory = httpx.get(f"{worker1_url}/memory/events").json()
        w1_user_msgs = [e for e in w1_memory["events"] if e["event_type"] == "user_message"]
        w1_found = any(task1_id in str(e["content"]) for e in w1_user_msgs)
        assert w1_found, "Worker-1 should have received task1"
        
        # Verify worker-2 received its task
        w2_memory = httpx.get(f"{worker2_url}/memory/events").json()
        w2_user_msgs = [e for e in w2_memory["events"] if e["event_type"] == "user_message"]
        w2_found = any(task2_id in str(e["content"]) for e in w2_user_msgs)
        assert w2_found, "Worker-2 should have received task2"
        
        # Verify task isolation (worker-1 should NOT have task2_id)
        w1_has_task2 = any(task2_id in str(e["content"]) for e in w1_user_msgs)
        assert not w1_has_task2, "Worker-1 should NOT have worker-2's task"
        
        w2_has_task1 = any(task1_id in str(e["content"]) for e in w2_user_msgs)
        assert not w2_has_task1, "Worker-2 should NOT have worker-1's task"
        
        logger.info("✓ Both workers processed their respective tasks correctly")
    
    def test_coordinator_memory_isolation(self, delegation_cluster):
        """Test coordinator's memory only contains its own delegation events."""
        coord_url = delegation_cluster["urls"]["coordinator"]
        
        # Get coordinator memory
        coord_memory = httpx.get(f"{coord_url}/memory/events").json()
        coord_events = coord_memory["events"]
        
        # Coordinator should only have delegation_request and delegation_response events
        # (not user_message from workers)
        event_types = set(e["event_type"] for e in coord_events)
        
        # These are valid for coordinator
        valid_types = {"delegation_request", "delegation_response"}
        
        # All coordinator events should be delegation-related
        for event in coord_events:
            assert event["event_type"] in valid_types, \
                f"Coordinator should only have delegation events, found: {event['event_type']}"
        
        logger.info("✓ Coordinator memory contains only delegation events")


class TestConcurrentDelegation:
    """Tests for concurrent delegation scenarios."""
    
    def test_sequential_delegations(self, delegation_cluster):
        """Test multiple sequential delegations work correctly."""
        coord_url = delegation_cluster["urls"]["coordinator"]
        
        # Send 5 sequential delegations
        responses = []
        for i in range(5):
            resp = httpx.post(
                f"{coord_url}/agent/delegate",
                json={"agent": "worker-1", "task": f"Sequential task {i}"},
                timeout=60.0
            )
            responses.append(resp)
        
        # All should succeed
        for i, resp in enumerate(responses):
            assert resp.status_code == 200, f"Delegation {i} failed"
            assert resp.json()["status"] == "completed"
        
        logger.info("✓ Sequential delegations work correctly")
    
    def test_alternating_delegations(self, delegation_cluster):
        """Test alternating between workers."""
        coord_url = delegation_cluster["urls"]["coordinator"]
        
        workers = ["worker-1", "worker-2"]
        
        for i in range(4):
            worker = workers[i % 2]
            resp = httpx.post(
                f"{coord_url}/agent/delegate",
                json={"agent": worker, "task": f"Alternating task {i}"},
                timeout=60.0
            )
            assert resp.status_code == 200
            assert resp.json()["agent"] == worker
        
        logger.info("✓ Alternating delegations work correctly")
