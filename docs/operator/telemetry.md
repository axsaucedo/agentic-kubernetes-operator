# OpenTelemetry

KAOS supports OpenTelemetry for observability, including distributed tracing, metrics, and log correlation across all agent operations.

## Overview

When enabled, OpenTelemetry instrumentation provides:

- **Tracing**: Distributed traces across agent requests, model calls, tool executions, and delegations
- **Metrics**: Counters and histograms for requests, latency, and error rates
- **Log Correlation**: Automatic injection of trace_id and span_id into log entries

## Enabling Telemetry

Add a `telemetry` section to your Agent's config:

```yaml
apiVersion: kaos.tools/v1alpha1
kind: Agent
metadata:
  name: my-agent
spec:
  modelAPI: my-modelapi
  model: "openai/gpt-4o"
  config:
    description: "Agent with OpenTelemetry enabled"
    telemetry:
      enabled: true
      endpoint: "http://otel-collector.monitoring.svc.cluster.local:4317"
      insecure: true
```

## Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Enable OpenTelemetry instrumentation |
| `endpoint` | string | `http://localhost:4317` | OTLP exporter endpoint |
| `insecure` | bool | `true` | Use insecure connection (no TLS) |
| `serviceName` | string | Agent name | Service name for traces/metrics |
| `tracesEnabled` | bool | `true` | Enable trace collection |
| `metricsEnabled` | bool | `true` | Enable metrics collection |
| `logCorrelation` | bool | `true` | Inject trace context into logs |

## Trace Spans

The following spans are automatically created:

### agent.process_message

Root span for each request to the agent. Attributes:
- `agent.name`: Name of the agent
- `session.id`: Session identifier

### agent.step.{n}

Span for each iteration of the agentic reasoning loop. Attributes:
- `agent.step`: Step number (1-based)
- `agent.name`: Agent name

### model.inference

Span for LLM API calls. Attributes:
- `model.name`: Model identifier
- `model.api_url`: API endpoint

### tool.{name}

Span for MCP tool executions. Attributes:
- `tool.name`: Tool name
- `mcp.server`: MCP server name

### delegate.{agent}

Span for agent-to-agent delegations. Attributes:
- `delegation.target`: Target agent name
- `delegation.task`: Task description

## Span Hierarchy Example

```
agent.process_message (SERVER)
├── agent.step.1 (INTERNAL)
│   └── model.inference (CLIENT)
├── agent.step.2 (INTERNAL)
│   ├── model.inference (CLIENT)
│   └── tool.calculator (CLIENT)
├── agent.step.3 (INTERNAL)
│   ├── model.inference (CLIENT)
│   └── delegate.researcher (CLIENT)
└── agent.step.4 (INTERNAL)
    └── model.inference (CLIENT)
```

## Metrics

The following metrics are collected:

| Metric | Type | Description |
|--------|------|-------------|
| `kaos.agent.requests` | Counter | Total requests processed |
| `kaos.agent.request.duration` | Histogram | Request duration in seconds |
| `kaos.model.calls` | Counter | Total model API calls |
| `kaos.model.duration` | Histogram | Model call duration in seconds |
| `kaos.tool.calls` | Counter | Total tool executions |
| `kaos.tool.duration` | Histogram | Tool execution duration in seconds |
| `kaos.delegations` | Counter | Total agent delegations |
| `kaos.delegation.duration` | Histogram | Delegation duration in seconds |

All metrics include labels:
- `agent_name`: Name of the agent
- `status`: "success" or "error"

Tool metrics also include:
- `tool_name`: Name of the tool
- `mcp_server`: Name of the MCP server

Delegation metrics also include:
- `target_agent`: Name of the target agent

## Log Correlation

When `logCorrelation` is enabled, log entries include trace context:

```
2024-01-15 10:30:45 INFO [trace_id=abc123 span_id=def456] Processing message...
```

This allows correlating logs with traces in your observability backend.

## Example: Agent with Full Telemetry

```yaml
apiVersion: kaos.tools/v1alpha1
kind: Agent
metadata:
  name: traced-agent
spec:
  modelAPI: my-modelapi
  model: "openai/gpt-4o"
  mcpServers:
  - calculator
  config:
    description: "Agent with full OpenTelemetry observability"
    instructions: "You are a helpful assistant with calculator access."
    telemetry:
      enabled: true
      endpoint: "http://otel-collector.monitoring.svc.cluster.local:4317"
      insecure: true
      serviceName: "traced-agent"
      tracesEnabled: true
      metricsEnabled: true
      logCorrelation: true
  agentNetwork:
    access:
    - researcher
```

## Setting Up an OTel Collector

To collect telemetry, deploy an OpenTelemetry Collector in your cluster:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
  namespace: monitoring
data:
  config.yaml: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318

    processors:
      batch:
        timeout: 10s

    exporters:
      otlp:
        endpoint: "your-backend:4317"
        tls:
          insecure: true

    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch]
          exporters: [otlp]
        metrics:
          receivers: [otlp]
          processors: [batch]
          exporters: [otlp]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-collector
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: otel-collector
  template:
    metadata:
      labels:
        app: otel-collector
    spec:
      containers:
      - name: collector
        image: otel/opentelemetry-collector:latest
        args: ["--config=/etc/otel/config.yaml"]
        ports:
        - containerPort: 4317
          name: otlp-grpc
        - containerPort: 4318
          name: otlp-http
        volumeMounts:
        - name: config
          mountPath: /etc/otel
      volumes:
      - name: config
        configMap:
          name: otel-collector-config
---
apiVersion: v1
kind: Service
metadata:
  name: otel-collector
  namespace: monitoring
spec:
  selector:
    app: otel-collector
  ports:
  - port: 4317
    name: otlp-grpc
  - port: 4318
    name: otlp-http
```

## Using with SigNoz

[SigNoz](https://signoz.io/) is an open-source APM that works well with KAOS:

1. Deploy SigNoz in your cluster:
```bash
helm repo add signoz https://charts.signoz.io
helm install signoz signoz/signoz -n monitoring --create-namespace
```

2. Configure agents to send telemetry to SigNoz:
```yaml
config:
  telemetry:
    enabled: true
    endpoint: "http://signoz-otel-collector.monitoring.svc.cluster.local:4317"
```

3. Access the SigNoz UI to view traces, metrics, and logs.

## Using with Uptrace

[Uptrace](https://uptrace.dev/) is another excellent option:

1. Deploy Uptrace:
```bash
helm repo add uptrace https://charts.uptrace.dev
helm install uptrace uptrace/uptrace -n monitoring --create-namespace
```

2. Configure agents:
```yaml
config:
  telemetry:
    enabled: true
    endpoint: "http://uptrace.monitoring.svc.cluster.local:14317"
```

## Environment Variables

For advanced configuration, the following environment variables are passed to agent pods when telemetry is enabled:

| Variable | Description |
|----------|-------------|
| `OTEL_ENABLED` | "true" when telemetry is enabled |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint URL |
| `OTEL_EXPORTER_OTLP_INSECURE` | "true" for insecure connections |
| `OTEL_SERVICE_NAME` | Service name for traces/metrics |
| `OTEL_TRACES_ENABLED` | "true" when traces are enabled |
| `OTEL_METRICS_ENABLED` | "true" when metrics are enabled |
| `OTEL_LOG_CORRELATION` | "true" when log correlation is enabled |

## Troubleshooting

### No traces appearing

1. Verify telemetry is enabled:
```bash
kubectl get agent my-agent -o jsonpath='{.spec.config.telemetry}'
```

2. Check agent logs for OTel initialization:
```bash
kubectl logs -l agent=my-agent | grep -i otel
```

3. Verify collector is reachable:
```bash
kubectl exec -it deploy/agent-my-agent -- curl -v http://otel-collector.monitoring:4317
```

### High latency

If telemetry adds noticeable latency:
- Use batching in the OTel collector
- Consider sampling for high-throughput agents
- Disable metrics if only traces are needed

### Missing spans

Ensure all sub-agents and MCP servers are instrumented:
- Each agent should have its own telemetry config
- MCP servers share the agent's trace context via W3C Trace Context headers
