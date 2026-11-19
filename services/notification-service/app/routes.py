import asyncio

from uuid import UUID

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app import repositories
from app.auth import authenticate_websocket, get_user_from_authorization
from app.config import settings
from app.realtime import notification_connections
from app.schemas import (
    FcmTokenDeleteRequest,
    FcmTokenRequest,
    PushSubscriptionRequest,
)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])
websocket_router = APIRouter()


@router.get("/push/vapid-public-key")
def get_vapid_public_key():
    if not settings.vapid_public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Web push is not configured",
        )
    return {"public_key": settings.vapid_public_key}


@router.get("")
async def list_notifications_route(
    limit: int = Query(50, ge=1, le=100),
    unread_only: bool = False,
    authorization: str | None = Header(default=None),
):
    user = await get_user_from_authorization(authorization)
    return await asyncio.to_thread(
        repositories.list_notifications,
        user["id"],
        limit,
        unread_only,
    )


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    authorization: str | None = Header(default=None),
):
    user = await get_user_from_authorization(authorization)
    updated = await asyncio.to_thread(
        repositories.mark_notification_read,
        str(notification_id),
        user["id"],
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return {"status": "read"}


@router.post("/read-all")
async def mark_all_read(
    authorization: str | None = Header(default=None),
):
    user = await get_user_from_authorization(authorization)
    count = await asyncio.to_thread(
        repositories.mark_all_notifications_read,
        user["id"],
    )
    return {"updated_count": count}


@router.post("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def save_subscription(
    subscription: PushSubscriptionRequest,
    authorization: str | None = Header(default=None),
):
    user = await get_user_from_authorization(authorization)
    await asyncio.to_thread(
        repositories.save_push_subscription,
        user["id"],
        str(subscription.endpoint),
        subscription.keys.p256dh,
        subscription.keys.auth,
    )


@router.post("/fcm-tokens", status_code=status.HTTP_204_NO_CONTENT)
async def register_fcm_token(
    token: FcmTokenRequest,
    authorization: str | None = Header(default=None),
):
    user = await get_user_from_authorization(authorization)
    await asyncio.to_thread(
        repositories.save_fcm_token,
        user["id"],
        token.token,
        token.platform,
    )


@router.delete("/fcm-tokens", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_fcm_token(
    token: FcmTokenDeleteRequest,
    authorization: str | None = Header(default=None),
):
    user = await get_user_from_authorization(authorization)
    await asyncio.to_thread(
        repositories.delete_fcm_token,
        user["id"],
        token.token,
    )


@websocket_router.websocket("/ws/notifications")
async def notification_websocket(websocket: WebSocket):
    await websocket.accept()
    user = await authenticate_websocket(websocket)
    if user is None:
        return

    await notification_connections.register(websocket, user["id"])
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await notification_connections.disconnect(websocket)
