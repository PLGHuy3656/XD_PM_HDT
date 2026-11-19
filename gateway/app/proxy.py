"""Reverse proxy forwarding, path security, and hop-by-hop header management."""
from __future__ import annotations

import logging
import re
from typing import AsyncIterator, List, Optional, Set, Tuple
import urllib.parse
import httpx
from fastapi import HTTPException, Request, Response, status
from starlette.responses import StreamingResponse

from app.config import settings

logger = logging.getLogger("gateway.proxy")

# Standard HTTP hop-by-hop headers per RFC 2616 §13.5.1 / RFC 7230 §6.1
STANDARD_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

# Regex to detect dangerous path traversal and encoding attempts:
# - encoded dots (%2e, %252e)
# - encoded slashes (%2f, %252f)
# - encoded backslashes (%5c, %255c)
# - encoded null bytes (%00, %2500)
# - ambiguous delimiters (%3f / ?, %23 / #, %253f, %2523)
# - literal dot-dot (..)
# - double/multiple slashes (//)
# - backslash (\)
# - semicolon (;)
# - hash (#)
DANGEROUS_PATTERNS_RE = re.compile(
    r"""
    (%2e|%2f|%5c|%00|%252e|%252f|%255c|%2500|%3f|%23|%253f|%2523)
    |(\.\.)
    |(//+)
    |([\\;#])
    """,
    re.IGNORECASE | re.VERBOSE,
)


def validate_path_security(request: Request, path: str = "") -> None:
    """Strictly validates request paths against traversal, dangerous encodings,

    ambiguous delimiters (%3f, %23, #), double slashes, backslashes, and internal endpoint probing.
    """
    # 1. Extract raw_path directly from ASGI scope
    raw_path_bytes = request.scope.get("raw_path")
    if raw_path_bytes:
        raw_path_str = raw_path_bytes.decode("latin1", errors="ignore")
    else:
        raw_path_str = request.url.path

    # Check for ambiguous delimiters (%3f, %23, #) anywhere in raw path or path parameter
    if re.search(r"(%3[fF]|%23|#)", raw_path_str) or re.search(r"(%3[fF]|%23|#)", path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad Request: Path contains invalid encoding or ambiguous path delimiters",
        )

    # Isolate path portion before query parameters
    raw_path_only = raw_path_str.split("?")[0]

    # Reject dangerous encodings, dot segments, double slash, backslash
    if DANGEROUS_PATTERNS_RE.search(raw_path_only) or DANGEROUS_PATTERNS_RE.search(path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad Request: Path contains invalid encoding or path traversal sequences",
        )

    # 2. Multi-pass decoding to catch obfuscated/double-encoded sequences
    decoded = urllib.parse.unquote(raw_path_only)
    double_decoded = urllib.parse.unquote(decoded)

    for candidate in (raw_path_only, decoded, double_decoded, path):
        normalized = candidate.replace("\\", "/").lower()
        segments = [s.strip() for s in normalized.split("/") if s.strip()]

        # Strictly block client access to any /internal endpoint
        if "internal" in segments:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Direct access to internal endpoints is prohibited",
            )

        # Reject any residual dot segments
        if ".." in segments or "." in segments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bad Request: Path contains invalid encoding or path traversal sequences",
            )


def extract_hop_by_hop_headers(raw_headers: list[tuple[bytes, bytes]]) -> Set[str]:
    """Extracts standard hop-by-hop headers plus all headers dynamically listed

    in the 'Connection' header field (RFC 7230 §6.1).
    """
    hop_by_hop = set(STANDARD_HOP_BY_HOP)
    for k, v in raw_headers:
        if k.decode("latin1", errors="ignore").lower() == "connection":
            val = v.decode("latin1", errors="ignore")
            for token in val.split(","):
                cleaned = token.strip().lower()
                if cleaned:
                    hop_by_hop.add(cleaned)
    return hop_by_hop


class ReverseProxyHandler:
    """Handles forwarding requests to upstream microservices with correlation tracking,

    connection pooling, streaming, and error normalization.
    """

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client

    def get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        limits = httpx.Limits(
            max_connections=settings.http_max_connections,
            max_keepalive_connections=settings.http_max_keepalive_connections,
            keepalive_expiry=settings.http_keepalive_expiry_seconds,
        )
        return httpx.AsyncClient(limits=limits)

    async def forward(
        self,
        request: Request,
        upstream_base_url: str,
        upstream_path: str,
        timeout: float,
        canonical_query: Optional[str] = None,
    ) -> Response:
        """Forwards incoming client request to upstream target."""
        # B1: Validate path security before building target URL
        validate_path_security(request, upstream_path)

        correlation_id = getattr(request.state, "correlation_id", "unknown-cid")
        client = getattr(request.app.state, "http_client", None) or self.get_client()

        # Build target URL cleanly
        target_url = f"{upstream_base_url.rstrip('/')}/{upstream_path.lstrip('/')}"
        if canonical_query is not None:
            if canonical_query:
                target_url = f"{target_url}?{canonical_query}"
        elif request.url.query:
            target_url = f"{target_url}?{request.url.query}"

        # B3 & Identity Sanitization:
        # Prepare request headers preserving multiple headers, stripping hop-by-hop,
        # and stripping all forged identity headers (X-User-*, X-Internal-*, X-Service-*, X-Forwarded-*)
        req_hop_by_hop = extract_hop_by_hop_headers(request.headers.raw)
        forward_headers: list[tuple[bytes, bytes]] = []

        for k, v in request.headers.raw:
            k_lower = k.decode("latin1", errors="ignore").lower()
            if k_lower in req_hop_by_hop or k_lower == "host":
                continue
            # Strip untrusted spoofed identity and proxy headers
            if (
                k_lower.startswith("x-user-")
                or k_lower.startswith("x-internal-")
                or k_lower.startswith("x-service-")
                or k_lower.startswith("x-forwarded-")
            ):
                continue
            forward_headers.append((k, v))

        # Inject trusted tracing & proxy headers
        forward_headers.append((b"x-correlation-id", correlation_id.encode("latin1")))
        client_host = request.client.host if request.client else "unknown"
        forward_headers.append((b"x-forwarded-for", client_host.encode("latin1")))
        forward_headers.append((b"x-forwarded-proto", request.url.scheme.encode("latin1")))
        forward_headers.append((b"x-forwarded-host", request.headers.get("host", "").encode("latin1")))

        # Inject authoritative verified identity headers if present in request state
        user = getattr(request.state, "user", None)
        if user:
            forward_headers.append((b"x-user-id", str(user.get("id", "")).encode("utf-8")))
            roles = user.get("roles") or []
            forward_headers.append((b"x-user-roles", ",".join(roles).encode("utf-8")))
            if user.get("email"):
                forward_headers.append((b"x-user-email", str(user["email"]).encode("utf-8")))

        # Read request body
        body = await request.body()

        try:
            req = client.build_request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=body if body else None,
                timeout=timeout,
            )

            # Segment boundary check on upstream URL:
            # req.url.path must strictly adhere to segment boundary of upstream_path
            clean_segments = [s for s in upstream_path.strip("/").split("/") if s]
            if len(clean_segments) >= 2:
                boundary_prefix = f"/{clean_segments[0]}/{clean_segments[1]}"
            else:
                boundary_prefix = f"/{clean_segments[0]}" if clean_segments else ""

            if boundary_prefix:
                boundary_slash = f"{boundary_prefix.rstrip('/')}/"
                if req.url.path != boundary_prefix and not req.url.path.startswith(boundary_slash):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Bad Request: Upstream path normalization escaped prefix boundary",
                    )

            upstream_response = await client.send(req, stream=True)

            # B3: Prepare response headers preserving duplicates (e.g. Set-Cookie)
            res_hop_by_hop = extract_hop_by_hop_headers(upstream_response.headers.raw)
            forward_res_headers: list[tuple[bytes, bytes]] = []
            has_correlation = False

            for k, v in upstream_response.headers.raw:
                k_lower = k.decode("latin1", errors="ignore").lower()
                if k_lower in res_hop_by_hop:
                    continue
                if k_lower == "x-correlation-id":
                    has_correlation = True
                forward_res_headers.append((k, v))

            if not has_correlation:
                forward_res_headers.append((b"x-correlation-id", correlation_id.encode("latin1")))

            # B2: Stream RAW un-decoded bytes to prevent decompressing body while preserving Content-Encoding
            async def _aiter_raw_stream() -> AsyncIterator[bytes]:
                if upstream_response.is_stream_consumed:
                    yield upstream_response.content
                else:
                    async for chunk in upstream_response.aiter_raw():
                        yield chunk

            response = StreamingResponse(
                _aiter_raw_stream(),
                status_code=upstream_response.status_code,
                background=upstream_response.aclose,
            )
            response.raw_headers = forward_res_headers
            return response

        except HTTPException:
            raise

        except httpx.TimeoutException as exc:
            logger.warning(
                "Upstream timeout [%s %s -> %s]: %s (cid=%s)",
                request.method,
                request.url.path,
                target_url,
                exc.__class__.__name__,
                correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Gateway Timeout: Upstream service did not respond within {timeout}s",
            ) from exc

        except httpx.ConnectError as exc:
            logger.warning(
                "Upstream connect error [%s %s -> %s]: %s (cid=%s)",
                request.method,
                request.url.path,
                target_url,
                exc.__class__.__name__,
                correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service Unavailable: Upstream service unreachable",
            ) from exc

        except Exception as exc:
            logger.error(
                "Proxy forwarding failure [%s %s -> %s]: %s (cid=%s)",
                request.method,
                request.url.path,
                target_url,
                exc.__class__.__name__,
                correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Bad Gateway: Error communicating with upstream service",
            ) from exc


proxy_handler = ReverseProxyHandler()
