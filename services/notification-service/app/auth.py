import asyncio

import httpx
from fastapi import HTTPException, WebSocket, WebSocketDisconnect, status

from app.config import settings


async def get_user_from_authorization(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is required",
        )

    url = f"{settings.management_service_url.rstrip('/')}/api/auth/me"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                url,
                headers={"Authorization": authorization},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Management authentication service unavailable",
        ) from exc

    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify access token",
        )

    user = response.json()
    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Authentication service returned an invalid user",
        )
    return user


async def authenticate_websocket(websocket: WebSocket) -> dict | None:
    try:
        message = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=5,
        )
    except (
        asyncio.TimeoutError,
        WebSocketDisconnect,
        RuntimeError,
        ValueError,
    ):
        await websocket.close(code=1008)
        return None

    if not isinstance(message, dict) or message.get("type") != "auth":
        await websocket.close(code=1008)
        return None

    try:
        return await get_user_from_authorization(
            message.get("authorization"),
        )
    except HTTPException as exc:
        await websocket.close(
            code=1008 if exc.status_code == 401 else 1011,
        )
        return None
