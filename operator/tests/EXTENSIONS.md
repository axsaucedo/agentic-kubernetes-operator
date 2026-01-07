# E2E Tests Migration - Extensions and Improvements Report

## Summary

This document outlines suggested improvements and extensions following the migration of E2E tests to use Gateway API for routing.

## Completed Changes

1. **Gateway API Integration**
   - All E2E tests now route through Gateway API instead of per-service port-forwarding
   - Operator installed via Helm with Gateway API enabled at test start
   - URL pattern: `/{namespace}/{resource-type}/{resource-name}/...`
   - HTTPRoute URL rewriting for path prefix stripping

2. **Test Infrastructure**
   - Session-scoped operator installation with file locking for xdist compatibility
   - `make clean` target for test resource cleanup
   - Removed obsolete `test_helm_install_e2e.py` (Helm install now in fixture)

3. **Performance**
   - Parallel execution: ~3 minutes (14 tests, 10 workers)
   - Sequential execution: ~7 minutes
   - No port-forward overhead per test

## Suggested Improvements

### High Priority

1. **Gateway API for Internal Agent Communication**
   - Currently agents communicate via Kubernetes Service DNS
   - Could optionally use Gateway URLs for cross-namespace communication
   - Benefits: Unified routing, potential for external agents
   - Implementation: Add `GATEWAY_URL` env var to agent pods, modify RemoteAgent

2. **TLS/HTTPS Support**
   - Add TLS listener configuration to Helm values
   - Generate or reference TLS certificates
   - Update HTTPRoutes for HTTPS backend policy

3. **Rate Limiting and Authentication**
   - Gateway API supports HTTPRoute filters for rate limiting
   - Could add BackendLBPolicy for circuit breaking
   - Consider adding JWT/API key authentication at Gateway level

### Medium Priority

4. **Custom Domain Support**
   - Add hostname-based routing option in HTTPRoutes
   - Allow users to configure custom domains per resource
   - Integrate with cert-manager for automatic TLS

5. **Observability Integration**
   - Add Prometheus metrics endpoint exposure via Gateway
   - Configure access logging at Gateway level
   - Add tracing headers propagation

6. **Cross-Namespace Communication**
   - Currently agents can only access peers in same namespace
   - Gateway API supports cross-namespace references
   - Consider ReferenceGrant for controlled cross-namespace access

7. **Load Balancing Policies**
   - Configure session affinity for stateful agents
   - Add retry policies for failed requests
   - Implement timeout configurations

### Low Priority

8. **gRPC Support**
   - Gateway API supports GRPCRoute for gRPC backends
   - Could enable gRPC streaming for agent communication
   - Requires protocol changes in agent server

9. **WebSocket Support**
   - For real-time agent streaming responses
   - Gateway controllers have varying WebSocket support
   - May need controller-specific configuration

10. **Multi-Cluster Gateway**
    - Envoy Gateway supports multi-cluster routing
    - Could enable geographically distributed agents
    - Requires significant infrastructure investment

## Technical Debt

1. **sh.py Deprecation Warnings**
   - Multi-threaded fork warnings in test output
   - Consider switching to subprocess directly or asyncio

2. **Test Cleanup Race Conditions**
   - Namespace deletion is async (`--wait=false`)
   - Could cause issues if tests run immediately after cleanup
   - Consider waiting for namespace termination

3. **Hardcoded GatewayClass Name**
   - Tests assume `envoy-gateway` GatewayClass
   - Should be configurable via environment variable

## Breaking Changes to Consider

1. **Default to Gateway API Enabled**
   - Currently defaults to disabled
   - Consider making Gateway API the default in future major version
   - Requires documentation and migration guide

2. **Remove Direct Service Access**
   - Once Gateway API is stable, could remove Service creation
   - Agents would only be accessible via Gateway
   - Breaking change requiring migration

## Next Steps

1. Implement TLS support (Issue #XX)
2. Add hostname-based routing (Issue #XX)
3. Create migration guide for existing installations
4. Benchmark Gateway API vs direct Service performance
5. Evaluate Gateway controller options (Envoy vs Kong vs Nginx)

---

*Generated: 2026-01-07*
*Tests: 14 passing*
*Parallel execution time: ~3 minutes*
