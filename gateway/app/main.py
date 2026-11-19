"""SwiftletCare API Gateway Application Entrypoint (CP11 Phase 1 & CP11.3)."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import (
    Instrumentator,
    metrics as pfi_metrics,
    routing as pfi_routing,
)

from app.config import settings
from app.middleware import CorrelationIdMiddleware, PathSecurityMiddleware
from app.routes import router as proxy_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gateway.main")

# FastAPI >=0.157 _IncludedRouter compatibility for prometheus-fastapi-instrumentator 7.x
_orig_get_route_name = getattr(pfi_routing, "_orig_get_route_name", pfi_routing._get_route_name)
pfi_routing._orig_get_route_name = _orig_get_route_name


def _compat_get_route_name(scope, routes, route_name=None):
    flat_routes = []
    for r in routes:
        if hasattr(r, "effective_route_contexts"):
            for ctx in r.effective_route_contexts():
                flat_routes.append(
                    ctx.starlette_route if getattr(ctx, "starlette_route", None) is not None else ctx
                )
        else:
            flat_routes.append(r)
    return _orig_get_route_name(scope, flat_routes, route_name)


pfi_routing._get_route_name = _compat_get_route_name
_default_instrumentation = pfi_metrics.default()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initializes shared AsyncClient pool on startup and gracefully closes it on shutdown."""
    owns_client = False
    if not hasattr(app.state, "http_client") or app.state.http_client is None:
        limits = httpx.Limits(
            max_connections=settings.http_max_connections,
            max_keepalive_connections=settings.http_max_keepalive_connections,
            keepalive_expiry=settings.http_keepalive_expiry_seconds,
        )
        client = httpx.AsyncClient(limits=limits)
        app.state.http_client = client
        owns_client = True
        logger.info("Gateway HTTP client pool initialized")

    yield

    if owns_client and hasattr(app.state, "http_client") and app.state.http_client is not None:
        await app.state.http_client.aclose()
        logger.info("Gateway HTTP client pool closed")


def create_gateway_app() -> FastAPI:
    """Factory function for FastAPI Gateway application."""
    if not getattr(settings, "jwt_secret", None) or len(settings.jwt_secret.strip()) < 16:
        raise RuntimeError(
            "Gateway security configuration error: JWT_SECRET must be explicitly configured and at least 16 characters."
        )

    application = FastAPI(
        title="SwiftletCare API Gateway",
        description="Unified L7 API Gateway providing reverse proxy routing, correlation ID tracing, JWT auth, and upstream aggregation.",
        version=settings.version,
        lifespan=lifespan,
    )

    # Middlewares (added in reverse order: CorrelationIdMiddleware executes first, then PathSecurityMiddleware)
    application.add_middleware(PathSecurityMiddleware)
    application.add_middleware(CorrelationIdMiddleware)

    # CORS middleware
    origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    if "*" in origins:
        origins = ["*"]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health Check
    @application.get("/health", tags=["Gateway Health"])
    def health():
        return {
            "status": "ok",
            "service": settings.service_name,
            "version": settings.version,
            "upstreams": {
                "management": settings.management_service_url,
                "iot": settings.iot_service_url,
                "ai": settings.ai_service_url,
                "notification": settings.notification_service_url,
                "analytics": settings.analytics_service_url,
            },
        }

    # Reverse proxy routes
    application.include_router(proxy_router)

    # Prometheus Metrics Instrumentation (CP10-B2)
    inst = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=False,
        excluded_handlers=["/metrics", "/health", "/docs", "/openapi.json"],
    )
    if _default_instrumentation is not None:
        inst.add(_default_instrumentation)
    inst.instrument(application).expose(application, endpoint="/metrics")

    return application


app = create_gateway_app()
