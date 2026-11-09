"""Correlation ID, tracing, and path security middleware for SwiftletCare API Gateway."""
from __future__ import annotations

import logging
import time
import uuid
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.proxy import validate_path_security

logger = logging.getLogger("gateway.middleware")

CORRELATION_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts or generates a correlation ID for request tracing.

    Sets X-Correlation-ID header on outgoing response and request.state.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = (
            request.headers.get(CORRELATION_HEADER)
            or request.headers.get(REQUEST_ID_HEADER)
            or str(uuid.uuid4())
        )

        request.state.correlation_id = correlation_id
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers[CORRELATION_HEADER] = correlation_id

        logger.info(
            "%s %s %d (%.2f ms) [cid=%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            correlation_id,
        )

        return response


class PathSecurityMiddleware(BaseHTTPMiddleware):
    """L7 edge security middleware: validates raw paths before route dispatching or authentication.

    Blocks path traversal, ambiguous delimiters (%3f, %23, #), and direct client access to /internal.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = getattr(request.state, "correlation_id", "unknown-cid")
        try:
            validate_path_security(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers={CORRELATION_HEADER: correlation_id},
            )

        return await call_next(request)
