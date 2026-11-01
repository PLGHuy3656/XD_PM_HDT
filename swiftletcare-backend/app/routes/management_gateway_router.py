import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status

from app.config.settings import settings

router = APIRouter(
    prefix="/api/management",
    tags=["Management Gateway"],
)

ALLOWED_MANAGEMENT_RESOURCES = {
    "auth",
    "devices",
    "farms",
    "technicians",
    "zones",
}
FORWARDED_HEADERS = ("accept", "authorization", "content-type")
FORWARDED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


@router.api_route(
    "/{path:path}",
    methods=FORWARDED_METHODS,
)
async def proxy_management_request(path: str, request: Request) -> Response:
    resource = path.partition("/")[0]
    if resource not in ALLOWED_MANAGEMENT_RESOURCES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Management endpoint not found",
        )

    upstream_url = (
        f"{settings.management_service_url.rstrip('/')}/api/{path}"
    )
    headers = {
        name: request.headers[name]
        for name in FORWARDED_HEADERS
        if name in request.headers
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            upstream = await client.request(
                request.method,
                upstream_url,
                params=request.query_params.multi_items(),
                content=await request.body(),
                headers=headers,
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Management service unavailable",
        ) from exc

    response_headers = {}
    content_type = upstream.headers.get("content-type")
    if content_type:
        response_headers["content-type"] = content_type

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )
