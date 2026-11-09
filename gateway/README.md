# SwiftletCare API Gateway Service (CP11 Phase 1)

Unified L7 API Gateway for SwiftletCare / NestMate microservices architecture.

## Overview
The API Gateway acts as the single entry point for all frontend and mobile client traffic, routing requests to upstream microservices:
- **Management Service**: Authentication, Farm, Zone, Device Registry, Technician management.
- **IoT Service**: Telemetry history, device presence, remote relay and environmental threshold commands.
- **AI Service**: Camera registries, runtime status, bird counting, detections, and snapshots.
- **Notification Service**: Operational alerts, notification items, user push devices.
- **Analytics Service**: Analytical warehouse, aggregations, trend correlations (CP9 target).

## Phase 1 Capabilities (Skeleton)
- **Health Endpoint**: `GET /health` with upstream configuration inventory.
- **Environment-based Configuration**: 100% dynamic upstream base URLs and timeouts via `.env` or system environment variables.
- **HTTP Reverse Proxy Routing**: Non-blocking asynchronous streaming proxy via `httpx.AsyncClient` with connection pooling.
- **Correlation ID Tracking**: Automatic propagation and generation of `X-Correlation-ID` across client, gateway, and upstream services.
- **Security Guard**: Explicit blocking of internal endpoints (`/internal/*`).
- **Standardized Error Normalization**: JSON responses for 502 Bad Gateway, 503 Service Unavailable, and 504 Gateway Timeout.

## Security Configuration (CP11.3 & CP11.3-R5-A)
- **JWT_SECRET (Required)**: Must be explicitly configured (minimum 16 characters). There is no hardcoded fallback; the Gateway fails fast at configuration load and startup if this secret is missing, empty, or too short. Secrets are never printed in logs or error messages.
- **ANALYTICS_SERVICE_DEPLOYED (Fail-Closed)**: Explicit boolean flag controlling forwarding to Analytics Service endpoints (`/api/v1/analytics/*`). Defaults to `false`. When `false` (or when `ENVIRONMENT` or the flag is missing), all Analytics proxy requests immediately return `503 Service Unavailable` (`SERVICE_NOT_DEPLOYED: Analytics Service is not yet deployed`) with zero upstream requests forwarded.
- **Security Check Precedence**: Authentication (401) and RBAC/tenant isolation (403) checks are always evaluated *before* the Analytics deployment check, preventing unauthenticated callers from probing upstream deployment status.

## Running Locally
```bash
# Ensure JWT_SECRET is set before starting
export JWT_SECRET="your-secure-gateway-secret-key-at-least-16-chars"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
