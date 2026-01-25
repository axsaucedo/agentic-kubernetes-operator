"""
OpenTelemetry Manager for KAOS.

Provides a simplified interface for OpenTelemetry instrumentation using standard
OTEL_* environment variables. When OTEL_ENABLED=true, traces, metrics, and log
correlation are all enabled.
"""

import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.propagate import set_global_textmap, inject, extract
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.trace import Span, SpanKind, Status, StatusCode
from opentelemetry.context import Context

logger = logging.getLogger(__name__)

# Semantic conventions for KAOS spans
ATTR_AGENT_NAME = "agent.name"
ATTR_SESSION_ID = "session.id"
ATTR_MODEL_NAME = "gen_ai.request.model"
ATTR_TOOL_NAME = "tool.name"
ATTR_DELEGATION_TARGET = "agent.delegation.target"

# Process-global initialization state
_initialized: bool = False


@dataclass
class OtelConfig:
    """OpenTelemetry configuration from environment variables."""

    enabled: bool
    service_name: str
    endpoint: str

    @classmethod
    def from_env(cls, default_service_name: str = "kaos") -> "OtelConfig":
        """Create config from standard OTEL_* environment variables."""
        return cls(
            enabled=os.getenv("OTEL_ENABLED", "false").lower() in ("true", "1", "yes"),
            service_name=os.getenv("OTEL_SERVICE_NAME", default_service_name),
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
        )


def init_otel(service_name: Optional[str] = None) -> bool:
    """Initialize OpenTelemetry with standard OTEL_* env vars.

    Should be called once at process startup. Idempotent - safe to call multiple times.

    Args:
        service_name: Default service name if OTEL_SERVICE_NAME not set

    Returns:
        True if OTel was initialized, False if disabled or already initialized
    """
    global _initialized
    if _initialized:
        return False

    config = OtelConfig.from_env(service_name or "kaos")
    if not config.enabled:
        logger.debug("OpenTelemetry disabled (OTEL_ENABLED != true)")
        _initialized = True
        return False

    # Create resource with service name
    resource = Resource.create({SERVICE_NAME: config.service_name})

    # Set up W3C Trace Context propagation
    set_global_textmap(
        CompositePropagator([TraceContextTextMapPropagator(), W3CBaggagePropagator()])
    )

    # Initialize tracing
    tracer_provider = TracerProvider(resource=resource)
    otlp_span_exporter = OTLPSpanExporter(endpoint=config.endpoint, insecure=True)
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Initialize metrics
    otlp_metric_exporter = OTLPMetricExporter(endpoint=config.endpoint, insecure=True)
    metric_reader = PeriodicExportingMetricReader(otlp_metric_exporter)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    logger.info(f"OpenTelemetry initialized: {config.endpoint} (service: {config.service_name})")
    _initialized = True
    return True


def is_otel_enabled() -> bool:
    """Check if OTel is enabled via environment variable."""
    return os.getenv("OTEL_ENABLED", "false").lower() in ("true", "1", "yes")


class KaosOtelManager:
    """Lightweight helper for creating spans and recording metrics.

    Provides convenience methods for KAOS-specific telemetry. Each server/client
    should create one instance. The underlying providers are process-global.

    Example:
        otel = KaosOtelManager("my-agent")
        with otel.span("process_request", session_id="abc123") as span:
            # do work
            span.set_attribute("custom", "value")
    """

    def __init__(self, service_name: str):
        """Initialize manager with service context.

        Args:
            service_name: Name of the service (e.g., agent name)
        """
        self.service_name = service_name
        self._tracer = trace.get_tracer(f"kaos.{service_name}")
        self._meter = metrics.get_meter(f"kaos.{service_name}")

        # Lazily initialized metrics
        self._request_counter: Optional[metrics.Counter] = None
        self._request_duration: Optional[metrics.Histogram] = None
        self._model_counter: Optional[metrics.Counter] = None
        self._model_duration: Optional[metrics.Histogram] = None
        self._tool_counter: Optional[metrics.Counter] = None
        self._tool_duration: Optional[metrics.Histogram] = None
        self._delegation_counter: Optional[metrics.Counter] = None
        self._delegation_duration: Optional[metrics.Histogram] = None

    def _ensure_metrics(self) -> None:
        """Lazily initialize metric instruments."""
        if self._request_counter is not None:
            return

        self._request_counter = self._meter.create_counter(
            "kaos.requests", description="Request count", unit="1"
        )
        self._request_duration = self._meter.create_histogram(
            "kaos.request.duration", description="Request duration", unit="ms"
        )
        self._model_counter = self._meter.create_counter(
            "kaos.model.calls", description="Model API call count", unit="1"
        )
        self._model_duration = self._meter.create_histogram(
            "kaos.model.duration", description="Model API call duration", unit="ms"
        )
        self._tool_counter = self._meter.create_counter(
            "kaos.tool.calls", description="Tool call count", unit="1"
        )
        self._tool_duration = self._meter.create_histogram(
            "kaos.tool.duration", description="Tool call duration", unit="ms"
        )
        self._delegation_counter = self._meter.create_counter(
            "kaos.delegations", description="Delegation count", unit="1"
        )
        self._delegation_duration = self._meter.create_histogram(
            "kaos.delegation.duration", description="Delegation duration", unit="ms"
        )

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        session_id: Optional[str] = None,
        **attributes: Any,
    ) -> Iterator[Span]:
        """Create a span with automatic end and status handling.

        Args:
            name: Span name
            kind: Span kind (INTERNAL, CLIENT, SERVER)
            session_id: Optional session ID to attach
            **attributes: Additional span attributes

        Yields:
            The active span
        """
        attrs = {ATTR_AGENT_NAME: self.service_name}
        if session_id:
            attrs[ATTR_SESSION_ID] = session_id
        attrs.update({k: v for k, v in attributes.items() if v is not None})

        with self._tracer.start_as_current_span(name, kind=kind, attributes=attrs) as span:
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    @contextmanager
    def model_span(self, model_name: str) -> Iterator[Span]:
        """Create a span for model API calls."""
        with self.span("model.inference", SpanKind.CLIENT, **{ATTR_MODEL_NAME: model_name}) as s:
            yield s

    @contextmanager
    def tool_span(self, tool_name: str) -> Iterator[Span]:
        """Create a span for tool execution."""
        with self.span(f"tool.{tool_name}", SpanKind.CLIENT, **{ATTR_TOOL_NAME: tool_name}) as s:
            yield s

    @contextmanager
    def delegation_span(self, target_agent: str) -> Iterator[Span]:
        """Create a span for A2A delegation."""
        with self.span(
            f"delegate.{target_agent}", SpanKind.CLIENT, **{ATTR_DELEGATION_TARGET: target_agent}
        ) as s:
            yield s

    def record_request(self, duration_ms: float, success: bool = True) -> None:
        """Record request metrics."""
        self._ensure_metrics()
        labels = {"agent.name": self.service_name, "success": str(success).lower()}
        if self._request_counter:
            self._request_counter.add(1, labels)
        if self._request_duration:
            self._request_duration.record(duration_ms, labels)

    def record_model_call(self, model: str, duration_ms: float, success: bool = True) -> None:
        """Record model API call metrics."""
        self._ensure_metrics()
        labels = {"agent.name": self.service_name, "model": model, "success": str(success).lower()}
        if self._model_counter:
            self._model_counter.add(1, labels)
        if self._model_duration:
            self._model_duration.record(duration_ms, labels)

    def record_tool_call(self, tool: str, duration_ms: float, success: bool = True) -> None:
        """Record tool call metrics."""
        self._ensure_metrics()
        labels = {"agent.name": self.service_name, "tool": tool, "success": str(success).lower()}
        if self._tool_counter:
            self._tool_counter.add(1, labels)
        if self._tool_duration:
            self._tool_duration.record(duration_ms, labels)

    def record_delegation(self, target: str, duration_ms: float, success: bool = True) -> None:
        """Record delegation metrics."""
        self._ensure_metrics()
        labels = {
            "agent.name": self.service_name,
            "target": target,
            "success": str(success).lower(),
        }
        if self._delegation_counter:
            self._delegation_counter.add(1, labels)
        if self._delegation_duration:
            self._delegation_duration.record(duration_ms, labels)

    @staticmethod
    def inject_context(carrier: Dict[str, str]) -> Dict[str, str]:
        """Inject trace context into headers for propagation."""
        inject(carrier)
        return carrier

    @staticmethod
    def extract_context(carrier: Dict[str, str]) -> Context:
        """Extract trace context from headers."""
        return extract(carrier)


@contextmanager
def timed() -> Iterator[Dict[str, float]]:
    """Context manager for timing operations.

    Yields a dict that will contain 'duration_ms' after the block.
    """
    result: Dict[str, float] = {}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["duration_ms"] = (time.perf_counter() - start) * 1000
