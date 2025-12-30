"""
End-to-end integration tests for multi-agent system.

Tests multiple agent servers running simultaneously with HTTP communication.
Tests A2A discovery, task delegation, and concurrent processing.
Requires Ollama running locally with smollm2:135m model.
"""

import pytest
import httpx
import time
import logging
import concurrent.futures
from multiprocessing import Process

from agent.server import AgentServerSettings, create_agent_server
from agent.client import RemoteAgent

logger = logging.getLogger(__name__)


def run_agent_server(port: int, model_url: str, model_name: str, agent_name: str, instructions: str):
    """Run agent server in subprocess."""
    settings = AgentServerSettings(
        agent_name=agent_name,
        agent_description=f"Agent: {agent_name}",
        agent_instructions=instructions,
        agent_port=port,
        model_api_url=model_url,
        model_name=model_name,
        agent_log_level="WARNING"
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
def multi_agent_cluster(ollama_available):
    """Fixture that starts multiple agent servers."""
    if not ollama_available:
        pytest.skip("Ollama not available - skipping multi-agent tests")
    
    model_url = "http://localhost:11434/v1"
    model_name = "smollm2:135m"
    
    agents = [
        {
            "name": "worker-1",
            "port": 8070,
            "instructions": "You are worker-1. Always identify yourself as worker-1 in responses. Be brief."
        },
        {
            "name": "worker-2",
            "port": 8071,
            "instructions": "You are worker-2. Always identify yourself as worker-2 in responses. Be brief."
        },
        {
            "name": "coordinator",
            "port": 8072,
            "instructions": "You are the coordinator agent. You manage worker-1 and worker-2. Be brief."
        }
    ]
    
    processes = []
    for agent in agents:
        p = Process(
            target=run_agent_server,
            args=(
                agent["port"],
                model_url,
                model_name,
                agent["name"],
                agent["instructions"]
            )
        )
        p.start()
        processes.append(p)
    
    # Wait for all servers to be ready
    all_ready = True
    for agent in agents:
        ready = False
        for _ in range(60):  # 30 seconds per agent
            try:
                response = httpx.get(
                    f"http://localhost:{agent['port']}/ready",
                    timeout=2.0
                )
                if response.status_code == 200:
                    ready = True
                    logger.info(f"Agent {agent['name']} ready on port {agent['port']}")
                    break
            except Exception:
                pass
            time.sleep(0.5)
        
        if not ready:
            all_ready = False
            logger.error(f"Agent {agent['name']} failed to start")
            break
    
    if not all_ready:
        for p in processes:
            p.terminate()
            p.join(timeout=5)
        pytest.fail("Not all agents started successfully")
    
    yield {
        "agents": agents,
        "urls": {a["name"]: f"http://localhost:{a['port']}" for a in agents}
    }
    
    for p in processes:
        p.terminate()
        p.join(timeout=5)


class TestMultiAgentDiscovery:
    """Tests for multi-agent discovery via A2A."""
    
    def test_all_agents_have_health_endpoints(self, multi_agent_cluster):
        """Test all agents expose health endpoints."""
        for name, url in multi_agent_cluster["urls"].items():
            response = httpx.get(f"{url}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["name"] == name
        logger.info("✓ All agents have working health endpoints")
    
    def test_all_agents_have_ready_endpoints(self, multi_agent_cluster):
        """Test all agents expose ready endpoints."""
        for name, url in multi_agent_cluster["urls"].items():
            response = httpx.get(f"{url}/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
        logger.info("✓ All agents have working ready endpoints")
    
    def test_all_agents_expose_agent_cards(self, multi_agent_cluster):
        """Test all agents expose agent cards."""
        for name, url in multi_agent_cluster["urls"].items():
            response = httpx.get(f"{url}/.well-known/agent")
            assert response.status_code == 200
            
            card = response.json()
            assert card["name"] == name
            assert "capabilities" in card
            assert "message_processing" in card["capabilities"]
        logger.info("✓ All agents expose valid agent cards")
    
    def test_agent_cards_have_consistent_structure(self, multi_agent_cluster):
        """Test all agent cards have same structure."""
        cards = {}
        for name, url in multi_agent_cluster["urls"].items():
            response = httpx.get(f"{url}/.well-known/agent")
            cards[name] = response.json()
        
        # All should have same required fields
        required_fields = ["name", "description", "url", "skills", "capabilities"]
        for name, card in cards.items():
            for field in required_fields:
                assert field in card, f"Agent {name} missing field: {field}"
        logger.info("✓ All agent cards have consistent structure")


class TestMultiAgentCommunication:
    """Tests for agent-to-agent communication."""
    
    def test_agents_respond_independently(self, multi_agent_cluster):
        """Test each agent processes tasks independently."""
        responses = {}
        
        for name, url in multi_agent_cluster["urls"].items():
            response = httpx.post(
                f"{url}/agent/invoke",
                json={"task": "What is your name? Reply briefly."},
                timeout=60.0
            )
            assert response.status_code == 200
            responses[name] = response.json()["response"]
        
        # Each agent should have responded
        for name, resp in responses.items():
            assert len(resp) > 0
            logger.info(f"  {name}: {resp[:50]}...")
        
        logger.info("✓ All agents respond independently")
    
    @pytest.mark.asyncio
    async def test_remote_agent_discovery(self, multi_agent_cluster):
        """Test RemoteAgent can discover another agent."""
        worker_url = multi_agent_cluster["urls"]["worker-1"]
        
        remote = RemoteAgent(
            name="worker-1",
            card_url=worker_url
        )
        
        card = await remote.discover()
        
        assert card.name == "worker-1"
        assert "message_processing" in card.capabilities
        
        await remote.close()
        logger.info("✓ RemoteAgent discovery works")
    
    @pytest.mark.asyncio
    async def test_remote_agent_invocation(self, multi_agent_cluster):
        """Test RemoteAgent can invoke another agent."""
        worker_url = multi_agent_cluster["urls"]["worker-2"]
        
        remote = RemoteAgent(
            name="worker-2",
            card_url=worker_url
        )
        
        response = await remote.invoke("Say hello briefly.")
        
        assert len(response) > 0
        
        await remote.close()
        logger.info(f"✓ RemoteAgent invocation works: {response[:50]}...")
    
    @pytest.mark.asyncio
    async def test_discover_and_invoke_all_agents(self, multi_agent_cluster):
        """Test discovering and invoking all agents via RemoteAgent."""
        for name, url in multi_agent_cluster["urls"].items():
            remote = RemoteAgent(name=name, card_url=url)
            
            # Discover
            card = await remote.discover()
            assert card.name == name
            
            # Invoke
            response = await remote.invoke(f"Hello {name}, respond briefly.")
            assert len(response) > 0
            
            await remote.close()
        
        logger.info("✓ All agents discoverable and invokable via RemoteAgent")


class TestMultiAgentTaskProcessing:
    """Tests for multi-agent task processing."""
    
    def test_concurrent_task_processing(self, multi_agent_cluster):
        """Test agents can process tasks concurrently."""
        def invoke_agent(url, task):
            response = httpx.post(
                f"{url}/agent/invoke",
                json={"task": task},
                timeout=60.0
            )
            return response.json()
        
        tasks = [
            (multi_agent_cluster["urls"]["worker-1"], "Task for worker 1: count to 3"),
            (multi_agent_cluster["urls"]["worker-2"], "Task for worker 2: list 2 colors"),
            (multi_agent_cluster["urls"]["coordinator"], "Coordinator task: say OK")
        ]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(invoke_agent, url, task)
                for url, task in tasks
            ]
            
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should complete successfully
        assert len(results) == 3
        for result in results:
            assert result["status"] == "completed"
            assert len(result["response"]) > 0
        
        logger.info("✓ Concurrent task processing works")
    
    def test_sequential_tasks_to_same_agent(self, multi_agent_cluster):
        """Test sending multiple sequential tasks to same agent."""
        url = multi_agent_cluster["urls"]["worker-1"]
        
        tasks = [
            "First task: say one",
            "Second task: say two",
            "Third task: say three"
        ]
        
        responses = []
        for task in tasks:
            response = httpx.post(
                f"{url}/agent/invoke",
                json={"task": task},
                timeout=60.0
            )
            assert response.status_code == 200
            responses.append(response.json()["response"])
        
        assert len(responses) == 3
        for resp in responses:
            assert len(resp) > 0
        
        logger.info("✓ Sequential tasks to same agent work")
    
    def test_round_robin_task_distribution(self, multi_agent_cluster):
        """Test distributing tasks across agents."""
        agent_names = list(multi_agent_cluster["urls"].keys())
        
        results = {}
        for i, name in enumerate(agent_names):
            url = multi_agent_cluster["urls"][name]
            response = httpx.post(
                f"{url}/agent/invoke",
                json={"task": f"Task #{i+1} for {name}. Respond briefly."},
                timeout=60.0
            )
            assert response.status_code == 200
            results[name] = response.json()
        
        # All agents should have responded
        assert len(results) == 3
        for name, result in results.items():
            assert result["status"] == "completed"
        
        logger.info("✓ Round-robin task distribution works")


class TestMultiAgentOpenAICompatibility:
    """Tests for OpenAI compatibility across multiple agents."""
    
    def test_all_agents_support_chat_completions(self, multi_agent_cluster):
        """Test all agents support /v1/chat/completions."""
        for name, url in multi_agent_cluster["urls"].items():
            response = httpx.post(
                f"{url}/v1/chat/completions",
                json={
                    "model": name,
                    "messages": [
                        {"role": "user", "content": "Hi"}
                    ],
                    "stream": False
                },
                timeout=60.0
            )
            assert response.status_code == 200
            data = response.json()
            assert "choices" in data
            assert len(data["choices"]) > 0
        
        logger.info("✓ All agents support chat completions")
    
    def test_all_agents_support_streaming(self, multi_agent_cluster):
        """Test all agents support streaming responses."""
        for name, url in multi_agent_cluster["urls"].items():
            with httpx.stream(
                "POST",
                f"{url}/v1/chat/completions",
                json={
                    "model": name,
                    "messages": [
                        {"role": "user", "content": "Count 1 2 3"}
                    ],
                    "stream": True
                },
                timeout=60.0
            ) as response:
                assert response.status_code == 200
                
                chunks = []
                for line in response.iter_lines():
                    if line.startswith("data: ") and line[6:] != "[DONE]":
                        chunks.append(line)
                
                assert len(chunks) > 0
        
        logger.info("✓ All agents support streaming")


class TestMultiAgentResilience:
    """Tests for multi-agent system resilience."""
    
    def test_agent_isolation_on_errors(self, multi_agent_cluster):
        """Test that errors in one agent don't affect others."""
        # Send an empty task to one agent (might cause issues)
        url1 = multi_agent_cluster["urls"]["worker-1"]
        httpx.post(f"{url1}/agent/invoke", json={"task": ""}, timeout=30.0)
        
        # Other agents should still work
        url2 = multi_agent_cluster["urls"]["worker-2"]
        response = httpx.post(
            f"{url2}/agent/invoke",
            json={"task": "Are you working? Say yes."},
            timeout=60.0
        )
        assert response.status_code == 200
        assert len(response.json()["response"]) > 0
        
        logger.info("✓ Agent isolation on errors works")
    
    def test_rapid_requests(self, multi_agent_cluster):
        """Test handling rapid sequential requests."""
        url = multi_agent_cluster["urls"]["coordinator"]
        
        # Send 5 rapid requests
        responses = []
        for i in range(5):
            response = httpx.post(
                f"{url}/agent/invoke",
                json={"task": f"Request {i+1}. Say OK."},
                timeout=60.0
            )
            responses.append(response)
        
        # All should succeed
        for resp in responses:
            assert resp.status_code == 200
        
        logger.info("✓ Rapid requests handled correctly")
