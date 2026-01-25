"""
OpenTelemetry instrumentation for KAOS.

Simple interface using standard OTEL_* environment variables.
When OTEL_ENABLED=true, traces, metrics, and log correlation are enabled.
"""

from agent.telemetry.manager import (
    OtelConfig,
    KaosOtelManager,
    init_otel,
    is_otel_enabled,
    timed,
)

__all__ = [
    "OtelConfig",
    "KaosOtelManager",
    "init_otel",
    "is_otel_enabled",
    "timed",
]
