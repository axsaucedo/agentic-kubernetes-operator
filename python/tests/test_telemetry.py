"""
Tests for OpenTelemetry instrumentation.
"""

import pytest
import os
import time
from unittest.mock import patch


class TestIsOtelEnabled:
    """Tests for is_otel_enabled utility."""

    def test_disabled_by_default(self):
        """Test that telemetry is disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            from agent.telemetry import is_otel_enabled

            assert is_otel_enabled() is False

    def test_enabled_with_true(self):
        """Test enabling with OTEL_ENABLED=true."""
        with patch.dict(os.environ, {"OTEL_ENABLED": "true"}, clear=True):
            from agent.telemetry import is_otel_enabled

            assert is_otel_enabled() is True

    def test_enabled_with_one(self):
        """Test enabling with OTEL_ENABLED=1."""
        with patch.dict(os.environ, {"OTEL_ENABLED": "1"}, clear=True):
            from agent.telemetry import is_otel_enabled

            assert is_otel_enabled() is True


class TestOtelConfig:
    """Tests for OtelConfig dataclass."""

    def test_from_env_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            from agent.telemetry.manager import OtelConfig

            config = OtelConfig.from_env()
            assert config.enabled is False
            assert config.service_name == "kaos"
            assert config.endpoint == "http://localhost:4317"

    def test_from_env_custom_values(self):
        """Test configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "OTEL_ENABLED": "true",
                "OTEL_SERVICE_NAME": "test-agent",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4317",
            },
            clear=True,
        ):
            from agent.telemetry.manager import OtelConfig

            config = OtelConfig.from_env()
            assert config.enabled is True
            assert config.service_name == "test-agent"
            assert config.endpoint == "http://collector:4317"

    def test_from_env_with_default_service_name(self):
        """Test from_env with custom default service name."""
        with patch.dict(os.environ, {}, clear=True):
            from agent.telemetry.manager import OtelConfig

            config = OtelConfig.from_env(default_service_name="my-agent")
            assert config.service_name == "my-agent"


class TestKaosOtelManager:
    """Tests for KaosOtelManager class."""

    def test_manager_creation(self):
        """Test creating a KaosOtelManager."""
        from agent.telemetry import KaosOtelManager

        manager = KaosOtelManager("test-agent")
        assert manager.service_name == "test-agent"

    def test_tracer_available(self):
        """Test getting a tracer from manager."""
        from agent.telemetry import KaosOtelManager

        manager = KaosOtelManager("test-agent")
        # Private attribute _tracer is used internally
        assert manager._tracer is not None

    def test_meter_available(self):
        """Test getting a meter from manager."""
        from agent.telemetry import KaosOtelManager

        manager = KaosOtelManager("test-agent")
        # Private attribute _meter is used internally
        assert manager._meter is not None

    def test_span_context_manager(self):
        """Test span context manager."""
        from agent.telemetry import KaosOtelManager

        manager = KaosOtelManager("test-agent")
        with manager.span("test-operation") as span:
            assert span is not None

    def test_record_request(self):
        """Test record_request doesn't raise errors."""
        from agent.telemetry import KaosOtelManager

        manager = KaosOtelManager("test-agent")
        # Should not raise - no stream parameter in new simplified API
        manager.record_request(100.0, success=True)

    def test_record_model_call(self):
        """Test record_model_call doesn't raise errors."""
        from agent.telemetry import KaosOtelManager

        manager = KaosOtelManager("test-agent")
        # Should not raise
        manager.record_model_call("gpt-4", 500.0, success=True)

    def test_record_tool_call(self):
        """Test record_tool_call doesn't raise errors."""
        from agent.telemetry import KaosOtelManager

        manager = KaosOtelManager("test-agent")
        # Should not raise
        manager.record_tool_call("calculator", 50.0, success=True)

    def test_record_delegation(self):
        """Test record_delegation doesn't raise errors."""
        from agent.telemetry import KaosOtelManager

        manager = KaosOtelManager("test-agent")
        # Should not raise
        manager.record_delegation("worker-1", 200.0, success=True)

    def test_model_span_context_manager(self):
        """Test model_span context manager."""
        from agent.telemetry import KaosOtelManager

        manager = KaosOtelManager("test-agent")
        with manager.model_span("gpt-4") as span:
            assert span is not None

    def test_tool_span_context_manager(self):
        """Test tool_span context manager."""
        from agent.telemetry import KaosOtelManager

        manager = KaosOtelManager("test-agent")
        with manager.tool_span("calculator") as span:
            assert span is not None

    def test_delegation_span_context_manager(self):
        """Test delegation_span context manager."""
        from agent.telemetry import KaosOtelManager

        manager = KaosOtelManager("test-agent")
        with manager.delegation_span("worker-1") as span:
            assert span is not None


class TestContextPropagation:
    """Tests for trace context propagation."""

    def test_inject_context(self):
        """Test context injection into headers."""
        from agent.telemetry import KaosOtelManager

        carrier: dict = {}
        result = KaosOtelManager.inject_context(carrier)
        # May or may not have traceparent depending on active span
        assert isinstance(result, dict)

    def test_extract_context(self):
        """Test context extraction from headers."""
        from agent.telemetry import KaosOtelManager

        carrier: dict = {}
        context = KaosOtelManager.extract_context(carrier)
        assert context is not None


class TestTimedContextManager:
    """Tests for timed context manager."""

    def test_timed_operation(self):
        """Test timed context manager tracks duration."""
        from agent.telemetry import timed

        with timed() as result:
            time.sleep(0.01)

        assert "duration_ms" in result
        assert result["duration_ms"] >= 10  # At least 10ms


class TestMCPServerTelemetrySimplified:
    """Tests for MCPServer simplified telemetry settings."""

    def test_otel_disabled_by_default(self):
        """Test that OTel is disabled by default for MCPServer."""
        with patch.dict(os.environ, {}, clear=True):
            from mcptools.server import MCPServer, MCPServerSettings

            settings = MCPServerSettings()
            server = MCPServer(settings)
            assert server._otel_enabled is False

    def test_otel_enabled_from_env(self):
        """Test that OTel can be enabled via OTEL_ENABLED env var."""
        with patch.dict(os.environ, {"OTEL_ENABLED": "true"}, clear=True):
            from mcptools.server import MCPServer, MCPServerSettings

            settings = MCPServerSettings()
            server = MCPServer(settings)
            assert server._otel_enabled is True
