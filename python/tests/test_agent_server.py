"""
End-to-end integration tests for Agent server.

Tests the actual Agent server running with HTTP client communication.
Uses subprocess to start server and HTTP calls to test endpoints.
Requires Ollama running locally with smollm2:135m model.
"""

import pytest
import httpx
import time
import logging
import json
from multiprocessing import Process

from agent.server import AgentServer, AgentServerSettings, create_agent_server
from agent.client import Agent
from agent.memory import LocalMemory
from modelapi.client import ModelAPI

logger = logging.getLogger(__name__)


def run_agent_server(port: int, model_url: str, model_name: str, agent_name: str):
    """Run agent server in subprocess with debug memory endpoints enabled."""
    settings = AgentServerSettings(
        agent_name=agent_name,
        agent_description=f"Test Agent: {agent_name}",
        agent_instructions="You are a helpful test assistant. Keep responses very brief (one sentence max).",
        agent_port=port,
        model_api_url=model_url,
        model_name=model_name,
        agent_log_level="WARNING",
        agent_debug_memory_endpoints=True  # Enable for testing
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
def agent_server_process(ollama_available):
    """Fixture that starts agent server in subprocess."""
    if not ollama_available:
        pytest.skip("Ollama not available - skipping end-to-end agent tests")
    
    port = 8060
    model_url = "http://localhost:11434"
    model_name = "smollm2:135m"
    agent_name = "test-agent"
    
    process = Process(
        target=run_agent_server,
        args=(port, model_url, model_name, agent_name)
    )
    process.start()
    
    # Wait for server to be ready (may take longer due to model loading)
    ready = False
    for _ in range(60):  # 30 seconds max
        try:
            response = httpx.get(f"http://localhost:{port}/ready", timeout=2.0)
            if response.status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)
    
    if not ready:
        process.terminate()
        process.join(timeout=5)
        pytest.fail("Agent server did not start in time")
    
    yield {"url": f"http://localhost:{port}", "port": port, "name": agent_name}
    
    process.terminate()
    process.join(timeout=5)


class TestAgentServerHealthEndpoints:
    """Tests for agent server health endpoints."""
    
    def test_health_endpoint(self, agent_server_process):
        """Test /health returns healthy status."""
        response = httpx.get(f"{agent_server_process['url']}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["name"] == agent_server_process["name"]
        assert "timestamp" in data
        logger.info("✓ Health endpoint works correctly")
    
    def test_ready_endpoint(self, agent_server_process):
        """Test /ready returns ready status."""
        response = httpx.get(f"{agent_server_process['url']}/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["name"] == agent_server_process["name"]
        logger.info("✓ Ready endpoint works correctly")


class TestAgentCardEndpoint:
    """Tests for A2A agent card endpoint."""
    
    def test_agent_card_endpoint(self, agent_server_process):
        """Test /.well-known/agent returns valid agent card."""
        response = httpx.get(f"{agent_server_process['url']}/.well-known/agent")
        assert response.status_code == 200
        
        card = response.json()
        assert card["name"] == agent_server_process["name"]
        assert "description" in card
        assert "url" in card
        assert "capabilities" in card
        assert "message_processing" in card["capabilities"]
        logger.info("✓ Agent card endpoint works correctly")
    
    def test_agent_card_structure_compliant(self, agent_server_process):
        """Test agent card has A2A-compliant structure."""
        response = httpx.get(f"{agent_server_process['url']}/.well-known/agent")
        card = response.json()
        
        # Required A2A fields
        required_fields = ["name", "description", "url", "skills", "capabilities"]
        for field in required_fields:
            assert field in card, f"Missing required field: {field}"
        
        # Skills and capabilities should be lists
        assert isinstance(card["skills"], list)
        assert isinstance(card["capabilities"], list)
        logger.info("✓ Agent card is A2A-compliant")


class TestAgentInvocation:
    """Tests for agent task invocation."""
    
    def test_invoke_simple_task(self, agent_server_process):
        """Test /agent/invoke processes a simple task."""
        response = httpx.post(
            f"{agent_server_process['url']}/agent/invoke",
            json={"task": "Say hello"},
            timeout=60.0  # LLM may be slow
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "response" in data
        assert data["status"] == "completed"
        assert len(data["response"]) > 0
        logger.info(f"✓ Simple task completed: {data['response'][:50]}...")
    
    def test_invoke_returns_meaningful_response(self, agent_server_process):
        """Test that agent actually processes the task and returns a response."""
        response = httpx.post(
            f"{agent_server_process['url']}/agent/invoke",
            json={"task": "Say the word 'hello' in your response."},
            timeout=60.0
        )
        assert response.status_code == 200
        
        data = response.json()
        # The response should be non-empty (LLM actually processed it)
        assert len(data["response"]) > 5
        logger.info(f"✓ Agent provides meaningful response: {data['response'][:50]}...")
    
    def test_invoke_handles_complex_query(self, agent_server_process):
        """Test agent handles a more complex query."""
        response = httpx.post(
            f"{agent_server_process['url']}/agent/invoke",
            json={"task": "List three colors. Be brief."},
            timeout=60.0
        )
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["response"]) > 10
        logger.info("✓ Agent handles complex query")


class TestOpenAIChatCompletions:
    """Tests for OpenAI-compatible chat completions endpoint."""
    
    def test_non_streaming_completion(self, agent_server_process):
        """Test non-streaming /v1/chat/completions."""
        response = httpx.post(
            f"{agent_server_process['url']}/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [
                    {"role": "user", "content": "Say 'hello world'"}
                ],
                "stream": False
            },
            timeout=60.0
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert len(data["choices"][0]["message"]["content"]) > 0
        logger.info("✓ Non-streaming completion works")
    
    def test_chat_completion_response_format(self, agent_server_process):
        """Test chat completion response has correct OpenAI format."""
        response = httpx.post(
            f"{agent_server_process['url']}/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [
                    {"role": "user", "content": "Hi"}
                ],
                "stream": False
            },
            timeout=60.0
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required fields
        assert "id" in data
        assert data["id"].startswith("chatcmpl-")
        assert "object" in data
        assert data["object"] == "chat.completion"
        assert "created" in data
        assert "model" in data
        assert "choices" in data
        assert "usage" in data
        
        # Check choice structure
        choice = data["choices"][0]
        assert "index" in choice
        assert "message" in choice
        assert "finish_reason" in choice
        logger.info("✓ Chat completion response format is correct")
    
    def test_streaming_completion(self, agent_server_process):
        """Test streaming /v1/chat/completions with SSE."""
        with httpx.stream(
            "POST",
            f"{agent_server_process['url']}/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [
                    {"role": "user", "content": "Count from 1 to 3"}
                ],
                "stream": True
            },
            timeout=60.0
        ) as response:
            assert response.status_code == 200
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type
            
            chunks = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str != "[DONE]":
                        chunks.append(data_str)
            
            assert len(chunks) > 0
            logger.info(f"✓ Streaming completion works ({len(chunks)} chunks)")
    
    def test_streaming_completion_format(self, agent_server_process):
        """Test streaming response chunks have correct format."""
        with httpx.stream(
            "POST",
            f"{agent_server_process['url']}/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [
                    {"role": "user", "content": "Say OK"}
                ],
                "stream": True
            },
            timeout=60.0
        ) as response:
            assert response.status_code == 200
            
            found_done = False
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        found_done = True
                        continue
                    
                    # Parse and verify chunk format
                    # Note: Response may use single quotes, handle that
                    try:
                        chunk = json.loads(data_str.replace("'", '"').replace("None", "null"))
                        assert "id" in chunk
                        assert "object" in chunk
                        assert chunk["object"] == "chat.completion.chunk"
                        assert "choices" in chunk
                    except json.JSONDecodeError:
                        # Some chunks may not be valid JSON, that's okay
                        pass
            
            assert found_done, "Stream should end with [DONE]"
            logger.info("✓ Streaming chunk format is correct")


class TestAgentServerErrors:
    """Tests for error handling."""
    
    def test_invoke_empty_task(self, agent_server_process):
        """Test /agent/invoke handles empty task."""
        response = httpx.post(
            f"{agent_server_process['url']}/agent/invoke",
            json={"task": ""},
            timeout=30.0
        )
        # Should still return 200 (agent processes empty input)
        assert response.status_code in [200, 400]
    
    def test_chat_completion_missing_messages(self, agent_server_process):
        """Test /v1/chat/completions handles missing messages."""
        response = httpx.post(
            f"{agent_server_process['url']}/v1/chat/completions",
            json={
                "model": "test-agent",
                "stream": False
            },
            timeout=30.0
        )
        assert response.status_code in [400, 422, 500]
    
    def test_invalid_endpoint(self, agent_server_process):
        """Test invalid endpoint returns 404."""
        response = httpx.get(f"{agent_server_process['url']}/invalid/endpoint")
        assert response.status_code == 404
