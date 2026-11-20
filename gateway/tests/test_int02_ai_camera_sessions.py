"""INT02: Gateway camera session / frames / stop routes (RBAC, forged body, internal key)."""
import json

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.test_auth_rbac import make_jwt_token

OWNER_A, OWNER_B, TECH_A, ADMIN, VIEWER = (
    "00000000-0000-0000-0000-00000000000a",
    "00000000-0000-0000-0000-00000000000b",
    "00000000-0000-0000-0000-00000000000c",
    "00000000-0000-0000-0000-00000000000d",
    "00000000-0000-0000-0000-00000000000e",
)
FARM_A, FARM_B = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
CAMS = {"CAM-01": (FARM_A, "ZONE-A1", {OWNER_A, TECH_A}), "CAM-02": (FARM_B, "ZONE-B1", {OWNER_B})}
AI_KEY = "A9xK2mP7qR4vW8zB3nL6tY1cF5hJ0dE2sU9wG4kM7pQ"
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(settings, "ai_internal_service_key", AI_KEY)
    state = {"ai_online": True, "ai_calls": []}

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        uid, roles = "anon", []
        if token:
            p = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
            uid, roles = str(p.get("sub")), p.get("roles", [])
        if str(settings.management_service_url) in url:
            if "/api/auth/me" in url:
                return httpx.Response(200, json={"id": uid, "email": "x@t.dev", "status": "ACTIVE", "roles": roles})
            if url.split("?")[0].rstrip("/").endswith("/api/farms"):
                mine = [{"farm_id": f, "id": f} for f, _z, users in CAMS.values() if "ADMIN" in roles or uid in users]
                return httpx.Response(200, json=mine)
            if "/api/farms/" in url:
                fid = url.split("/api/farms/")[-1].split("/")[0].split("?")[0]
                for farm, _z, users in CAMS.values():
                    if farm == fid:
                        ok = "ADMIN" in roles or uid in users
                        return httpx.Response(200 if ok else 403, json={"farm_id": fid} if ok else {"detail": "Forbidden"})
                return httpx.Response(404, json={"detail": "nf"})
            if "/api/cameras/" in url or "/api/devices/" in url:
                cid = url.rstrip("/").split("/")[-1].split("?")[0]
                if cid not in CAMS:
                    return httpx.Response(404, json={"detail": "Camera not found"})
                farm, zone, users = CAMS[cid]
                if "ADMIN" in roles or uid in users:
                    return httpx.Response(200, json={"node_id": cid, "farm_id": farm, "zone_id": zone, "device_type": "CAMERA"})
                return httpx.Response(403, json={"detail": "Forbidden"})
        if str(settings.ai_service_url) in url:
            if not state["ai_online"]:
                raise httpx.ConnectError("AI down")
            body = await request.aread()
            state["ai_calls"].append({
                "url": url, "key": request.headers.get("X-Internal-Service-Key"),
                "auth": request.headers.get("Authorization"),
                "body": json.loads(body) if body and request.headers.get("content-type", "").startswith("application/json") else len(body),
            })
            if url.endswith("/frames"):
                return httpx.Response(202, json={"accepted": True})
            if "/uploads" in url:
                return httpx.Response(200, json={"cameraId": url.split("/cameras/")[-1].split("/")[0], "status": "STARTING", "sourceMode": "UPLOADED_VIDEO"})
            if "/api/v1/ai/events" in url:
                return httpx.Response(200, json=[
                    {"eventId": "E-A", "eventType": "PREDATOR_DETECTED", "cameraId": "CAM-01", "farmId": FARM_A, "class": "rat", "confidence": 0.8},
                    {"eventId": "E-B", "eventType": "PREDATOR_DETECTED", "cameraId": "CAM-02", "farmId": FARM_B, "class": "snake", "confidence": 0.7},
                ])
            return httpx.Response(200, json={"cameraId": url.split("/cameras/")[-1].split("/")[0], "status": "STARTING"})
        return httpx.Response(599, json={"detail": "unexpected upstream"})

    app = create_gateway_app()
    app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with TestClient(app) as c:
        yield c, state


def _h(uid, role):
    return {"Authorization": f"Bearer {make_jwt_token(user_id=uid, roles=[role])}"}


def test_owner_starts_session_with_authoritative_farm_zone(env):
    c, s = env
    r = c.post("/api/v1/ai/cameras/CAM-01/session", json={"mode": "DEMO_VIDEO"}, headers=_h(OWNER_A, "FARM_OWNER"))
    assert r.status_code == 200, r.text
    call = s["ai_calls"][-1]
    assert call["url"].endswith("/api/v1/ai/cameras/CAM-01/sessions")
    assert call["body"] == {"mode": "DEMO_VIDEO", "farmId": FARM_A, "zoneId": "ZONE-A1"}
    assert call["key"] == AI_KEY


@pytest.mark.parametrize("body", [
    {"mode": "DEMO_VIDEO", "farmId": FARM_B},
    {"mode": "LOCAL_CAMERA", "zoneId": "ZONE-B1"},
    {"mode": "DEMO_VIDEO", "source": "rtsp://10.0.0.5/stream"},
    {"mode": "LAN_CAMERA"},
    {},
])
def test_forged_or_unsupported_session_body_rejected(env, body):
    c, s = env
    r = c.post("/api/v1/ai/cameras/CAM-01/session", json=body, headers=_h(OWNER_A, "FARM_OWNER"))
    assert r.status_code == 422
    assert s["ai_calls"] == []


@pytest.mark.parametrize("path,kw", [
    ("session", {"json": {"mode": "LOCAL_CAMERA"}}),
    ("session/stop", {}),
    ("frames", {"content": JPEG, "headers_extra": {"Content-Type": "image/jpeg"}}),
])
def test_cross_farm_owner_denied_and_ai_not_called(env, path, kw):
    c, s = env
    headers = {**_h(OWNER_A, "FARM_OWNER"), **kw.pop("headers_extra", {})}
    r = c.post(f"/api/v1/ai/cameras/CAM-02/{path}", headers=headers, **kw)
    assert r.status_code == 403
    assert s["ai_calls"] == []


def test_technician_assigned_allowed_unassigned_denied(env):
    c, s = env
    assert c.post("/api/v1/ai/cameras/CAM-01/session", json={"mode": "LOCAL_CAMERA"}, headers=_h(TECH_A, "TECHNICIAN")).status_code == 200
    assert c.post("/api/v1/ai/cameras/CAM-02/session", json={"mode": "LOCAL_CAMERA"}, headers=_h(TECH_A, "TECHNICIAN")).status_code == 403


def test_admin_allowed_any_camera(env):
    c, _ = env
    assert c.post("/api/v1/ai/cameras/CAM-02/session", json={"mode": "DEMO_VIDEO"}, headers=_h(ADMIN, "ADMIN")).status_code == 200


def test_unauthenticated_rejected(env):
    c, s = env
    assert c.post("/api/v1/ai/cameras/CAM-01/session", json={"mode": "DEMO_VIDEO"}).status_code == 401
    assert c.post("/api/v1/ai/cameras/CAM-01/frames", content=JPEG, headers={"Content-Type": "image/jpeg"}).status_code == 401
    assert s["ai_calls"] == []


def test_unknown_camera_denied(env):
    c, s = env
    r = c.post("/api/v1/ai/cameras/CAM-99/session", json={"mode": "DEMO_VIDEO"}, headers=_h(ADMIN, "ADMIN"))
    assert r.status_code in (403, 404)
    assert s["ai_calls"] == []


def test_frames_forwarded_with_internal_key_and_validated(env):
    c, s = env
    h = _h(OWNER_A, "FARM_OWNER")
    r = c.post("/api/v1/ai/cameras/CAM-01/frames", content=JPEG, headers={**h, "Content-Type": "image/jpeg"})
    assert r.status_code == 202
    assert s["ai_calls"][-1]["key"] == AI_KEY and s["ai_calls"][-1]["body"] == len(JPEG)
    assert c.post("/api/v1/ai/cameras/CAM-01/frames", content=b"x", headers={**h, "Content-Type": "text/plain"}).status_code == 415
    big = b"\x00" * 1_500_001
    assert c.post("/api/v1/ai/cameras/CAM-01/frames", content=big, headers={**h, "Content-Type": "image/jpeg"}).status_code == 413


def test_stop_forwards_to_ai_stop(env):
    c, s = env
    r = c.post("/api/v1/ai/cameras/CAM-01/session/stop", headers=_h(OWNER_A, "FARM_OWNER"))
    assert r.status_code == 200
    assert s["ai_calls"][-1]["url"].endswith("/api/v1/ai/cameras/CAM-01/stop")


def test_ai_down_returns_503(env):
    c, s = env
    s["ai_online"] = False
    r = c.post("/api/v1/ai/cameras/CAM-01/session", json={"mode": "DEMO_VIDEO"}, headers=_h(OWNER_A, "FARM_OWNER"))
    assert r.status_code == 503


MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 256


def test_video_upload_forwards_authoritative_farm_and_key(env):
    c, s = env
    r = c.post("/api/v1/ai/cameras/CAM-01/video?farmId=forged&zoneId=forged", content=MP4,
               headers={**_h(OWNER_A, "FARM_OWNER"), "Content-Type": "video/mp4"})
    assert r.status_code == 200, r.text
    call = s["ai_calls"][-1]
    assert "/api/v1/ai/cameras/CAM-01/uploads" in call["url"]
    assert f"farmId={FARM_A}" in call["url"] and "zoneId=ZONE-A1" in call["url"] and "forged" not in call["url"]
    assert call["key"] == AI_KEY and call["body"] == len(MP4)


def test_video_upload_cross_farm_type_and_auth(env):
    c, s = env
    h = _h(OWNER_A, "FARM_OWNER")
    assert c.post("/api/v1/ai/cameras/CAM-02/video", content=MP4, headers={**h, "Content-Type": "video/mp4"}).status_code == 403
    assert c.post("/api/v1/ai/cameras/CAM-01/video", content=MP4, headers={**h, "Content-Type": "video/x-msvideo"}).status_code == 415
    assert c.post("/api/v1/ai/cameras/CAM-01/video", content=MP4, headers={"Content-Type": "video/mp4"}).status_code == 401
    assert s["ai_calls"] == []


def test_video_upload_oversize_rejected(env):
    c, s = env
    big = b"\x00" * (64 * 1024 * 1024 + 1)
    r = c.post("/api/v1/ai/cameras/CAM-01/video", content=big, headers={**_h(OWNER_A, "FARM_OWNER"), "Content-Type": "video/mp4"})
    assert r.status_code == 413
    assert s["ai_calls"] == []


def test_farm_events_scoped_and_filtered(env):
    c, s = env
    r = c.get(f"/api/v1/ai/farms/{FARM_A}/events", headers=_h(OWNER_A, "FARM_OWNER"))
    assert r.status_code == 200
    assert [e["eventId"] for e in r.json()] == ["E-A"]  # defence in depth: foreign event dropped
    assert f"farmId={FARM_A}" in s["ai_calls"][-1]["url"]


def test_farm_events_cross_farm_denied(env):
    c, s = env
    r = c.get(f"/api/v1/ai/farms/{FARM_A}/events", headers=_h(OWNER_B, "FARM_OWNER"))
    assert r.status_code == 403
    assert s["ai_calls"] == []


def test_farm_events_technician_assigned_only(env):
    c, _ = env
    assert c.get(f"/api/v1/ai/farms/{FARM_A}/events", headers=_h(TECH_A, "TECHNICIAN")).status_code == 200
    assert c.get(f"/api/v1/ai/farms/{FARM_B}/events", headers=_h(TECH_A, "TECHNICIAN")).status_code == 403
