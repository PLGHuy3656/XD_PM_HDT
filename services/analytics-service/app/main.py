"""
Main FastAPI Application Entrypoint for Analytics Service.
"""
import psycopg
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator, routing as pfi_routing

from app.api.health import router as health_router
from app.api.summary import router as summary_router
from app.api.trends import router as trends_router
from app.services.analytics_service import FarmNotFoundError, InvalidPeriodError

app = FastAPI(
    title="SwiftletCare Analytics Service",
    description="OLAP read model and statistical reporting service for SwiftletCare",
    version="0.1.0",
)

# Exception Handlers
@app.exception_handler(psycopg.OperationalError)
async def postgres_operational_error_handler(request: Request, exc: psycopg.OperationalError):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": "DATABASE_UNAVAILABLE",
                "message": "Analytics database is temporarily unavailable. Please retry shortly.",
            }
        },
    )


@app.exception_handler(FarmNotFoundError)
async def farm_not_found_handler(request: Request, exc: FarmNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": {
                "code": "FARM_NOT_FOUND",
                "message": str(exc),
            }
        },
    )


@app.exception_handler(InvalidPeriodError)
async def invalid_period_handler(request: Request, exc: InvalidPeriodError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "INVALID_PERIOD",
                "message": str(exc),
            }
        },
    )


# Include Routers
app.include_router(health_router)
app.include_router(summary_router)
app.include_router(trends_router)

# Prometheus Metrics Instrumentation (CP10-B2)
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

Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=False,
    excluded_handlers=["/metrics", "/health", "/docs", "/openapi.json"],
).instrument(app).expose(app, endpoint="/metrics")
