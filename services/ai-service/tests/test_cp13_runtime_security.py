"""CP13 Security & Data Integrity Hardening — internal runtime endpoint negative tests.

No database, no YOLO run: the runtime manager is replaced by a recorder and the
Management camera registry by an in-process fake (plus httpx.MockTransport for the
real adapter). Covers R1 (service key), R2 (authoritative camera ownership) and
source/model allowlists.
"""
from __future__ import annotations

import secrets
from typing import Any, Dict, List

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import AI_PIPELINE_DIR, Settings, is_internal_key_acceptable, settings
from app.main import create_app
from app.ports.camera_registry import (
    CameraNotAuthorized,
    CameraRegistry,
    CameraRegistryUnauthorized,
    CameraRegistryUnavailable,
    ManagementCameraRegistry,
    RegisteredCamera,
)

FARM_1 = "a18d8eee-cb1a-4b00-b375-d505eb8128d7"
FARM_2 = "f8fc4fa7-0d27-4e0b-89c0-e676e0e73469"
CAM1_UUID = "c0000001-0000-0000-0000-000000000001"
CAM1 = RegisteredCamera(camera_uuid=CAM1_UUID, node_id="CAM-01", farm_id=FARM_1, zone_id=None)
CAM2 = RegisteredCamera(camera_uuid="c0000002-0000-0000-0000-000000000002", node_id="CAM-02", farm_id=FARM_2, zone_id=None)
SAMPLE = str(AI_PIPELINE_DIR / "data" / "samples" / "fixture_swiftlet_positive.avi")
PUBLISHED_KEY = "swiftlet-internal-ai-service-" + "key-2026"  # pre-hardening value, must be refused


class FakeRegistry(CameraRegistry):
    """token-A owns FARM_1 (CAM-01), token-B owns FARM_2 (CAM-02), token-admin sees both."""

    def __init__(self) -> None:
        self.calls: List[tuple[str, str]] = []

    def resolve_camera(self, camera_id: str, bearer_token: str) -> RegisteredCamera:
        self.calls.append((camera_id, bearer_token))
        if bearer_token == "token-down":
            raise CameraRegistryUnavailable("down")
        if bearer_token == "token-expired":
            raise CameraRegistryUnauthorized("expired")
        cams = {"CAM-01": CAM1, CAM1_UUID: CAM1, "CAM-02": CAM2}
        cam = cams.get(camera_id)
        if cam is None:  # unknown id or a non-CAMERA device (sensor)
            raise CameraNotAuthorized("not a registered camera")
        allowed = {"token-A": {FARM_1}, "token-B": {FARM_2}, "token-admin": {FARM_1, FARM_2}}
        if cam.farm_id not in allowed.get(bearer_token, set()):
            raise CameraNotAuthorized("not authorized")
        return cam


class RecordingManagerProxy:
    def __init__(self, real) -> None:
        self._real = real
        self.runs: List[Dict[str, Any]] = []

    def start_source_in_background(self, **kwargs):
        self.runs.append(kwargs)

    def run_source(self, **kwargs):
        self.runs.append(kwargs)
        raise AssertionError("sync run not expected in these tests")

    def __getattr__(self, item):
        return getattr(self._real, item)


@pytest.fixture()
def strong_key() -> str:
    return secrets.token_urlsafe(32)


@pytest.fixture()
def harness(monkeypatch, strong_key):
    monkeypatch.setattr(settings, "ai_runtime_internal_enabled", True)
    monkeypatch.setattr(settings, "ai_internal_service_key", strong_key)
    app = create_app(load_configured_cameras=False)
    registry = FakeRegistry()
    recorder = RecordingManagerProxy(app.state.runtime_manager)
    app.state.camera_registry = registry
    app.state.runtime_manager = recorder
    client = TestClient(app)
    return client, registry, recorder, strong_key


def _post(client, key, token, **body):
    headers = {}
    if key is not None:
        headers["X-Internal-Service-Key"] = key
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"cameraId": "CAM-01", "source": SAMPLE, "background": True}
    payload.update(body)
    return client.post("/internal/v1/runtime/run", json=payload, headers=headers)


# ---------------------------------------------------------------- R1: configuration & key

def test_defaults_disable_runtime_and_have_no_key(monkeypatch):
    for var in ("AI_RUNTIME_INTERNAL_ENABLED", "AI_INTERNAL_SERVICE_KEY"):
        monkeypatch.delenv(var, raising=False)
    fresh = Settings(_env_file=None)
    assert fresh.ai_runtime_internal_enabled is False
    assert fresh.ai_internal_service_key == ""
    assert "ai_internal_service_key" not in repr(fresh)


def test_published_short_and_low_entropy_keys_are_not_acceptable(strong_key):
    assert is_internal_key_acceptable(strong_key)
    assert not is_internal_key_acceptable("")
    assert not is_internal_key_acceptable(PUBLISHED_KEY)
    assert not is_internal_key_acceptable("a" * 64)
    assert not is_internal_key_acceptable(strong_key[:20])
    assert not is_internal_key_acceptable("swiftlet-internal-" + strong_key)


def test_runtime_disabled_by_flag_returns_403(harness, monkeypatch):
    client, registry, recorder, key = harness
    monkeypatch.setattr(settings, "ai_runtime_internal_enabled", False)
    r = _post(client, key, "token-A")
    assert r.status_code == 403
    assert recorder.runs == [] and registry.calls == []


@pytest.mark.parametrize("configured", ["", PUBLISHED_KEY, "short-key"])
def test_unconfigured_or_published_key_fails_closed(harness, monkeypatch, configured):
    client, registry, recorder, _ = harness
    monkeypatch.setattr(settings, "ai_internal_service_key", configured)
    r = _post(client, configured or "x", "token-A")
    assert r.status_code == 503
    assert configured not in r.text or configured == ""
    assert recorder.runs == [] and registry.calls == []


@pytest.mark.parametrize("sent", [None, "", "wrong-key", PUBLISHED_KEY])
def test_missing_or_invalid_key_denied(harness, sent):
    client, registry, recorder, key = harness
    r = _post(client, sent, "token-A")
    assert r.status_code == 401
    assert key not in r.text
    assert recorder.runs == [] and registry.calls == []


def test_missing_bearer_token_denied(harness):
    client, registry, recorder, key = harness
    r = _post(client, key, None)
    assert r.status_code == 401
    assert recorder.runs == [] and registry.calls == []


# ---------------------------------------------------------------- R2: authoritative ownership

def test_owner_runs_own_camera_with_registry_farm(harness):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-A")
    assert r.status_code == 200, r.text
    run = recorder.runs[-1]
    assert run["camera_id"] == "CAM-01"
    assert run["farm_id"] == FARM_1
    assert r.json()["farmId"] == FARM_1


def test_client_farm_id_is_never_trusted(harness):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-A", farmId=FARM_2)
    assert r.status_code == 403
    assert recorder.runs == []
    r = _post(client, key, "token-admin", farmId=FARM_2)
    assert r.status_code == 403
    assert recorder.runs == []


def test_matching_farm_assertion_is_accepted(harness):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-A", farmId=FARM_1.upper())
    assert r.status_code == 200
    assert recorder.runs[-1]["farm_id"] == FARM_1


def test_cross_farm_camera_denied(harness):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-B", cameraId="CAM-01")
    assert r.status_code == 403
    assert recorder.runs == []


@pytest.mark.parametrize("camera", ["CAM-FAKE-999", "SWC-DEMO-NODE-001"])
def test_unregistered_camera_or_sensor_denied(harness, camera):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-admin", cameraId=camera)
    assert r.status_code == 403
    assert "ENVIRONMENT" not in r.text
    assert recorder.runs == []


def test_uuid_is_canonicalized_to_node_id(harness):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-A", cameraId=CAM1_UUID)
    assert r.status_code == 200
    assert recorder.runs[-1]["camera_id"] == "CAM-01"
    assert r.json()["cameraId"] == "CAM-01"


def test_registry_unavailable_fails_closed(harness):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-down")
    assert r.status_code == 503
    assert recorder.runs == []


def test_registry_rejects_token(harness):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-expired")
    assert r.status_code == 401
    assert recorder.runs == []


def test_invalid_identifier_rejected_before_registry(harness):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-A", cameraId="../etc")
    assert r.status_code == 400
    assert registry.calls == []


# ---------------------------------------------------------------- allowlists

@pytest.mark.parametrize(
    "source,expected",
    [
        ("http://169.254.169.254/latest", 400),
        ("RTSP://cam.local/stream", 400),
        ("udp://0.0.0.0:1234", 400),
        ("file:///C:/Windows/win.ini", 400),
        ("services/ai-service/.env", 403),
        ("../../services/ai-service/.env", 403),
        ("C:/Windows/win.ini", 403),
        ("C:/definitely/not/here.avi", 403),
        ("ai-pipeline/data/samples/does_not_exist.avi", 404),
    ],
)
def test_source_allowlist(harness, source, expected):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-A", source=source)
    assert r.status_code == expected, r.text
    assert recorder.runs == []


@pytest.mark.parametrize("model", ["C:/Windows/notepad.exe", "ai-pipeline/models/other.pt", "../evil.pt"])
def test_arbitrary_model_rejected(harness, model):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-A", modelPath=model)
    assert r.status_code == 403
    assert recorder.runs == []


def test_unauthorized_caller_gets_no_source_oracle(harness):
    client, registry, recorder, key = harness
    r = _post(client, key, "token-B", source="ai-pipeline/data/samples/does_not_exist.avi")
    assert r.status_code == 403  # camera denial happens before any path probing


# ---------------------------------------------------------------- Management adapter

def _adapter(handler) -> ManagementCameraRegistry:
    return ManagementCameraRegistry("http://mgmt.test", transport=httpx.MockTransport(handler))


def test_adapter_maps_registry_responses():
    def ok(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer tok"
        assert request.url.path == f"/api/cameras/{CAM1_UUID}"
        return httpx.Response(200, json={"device_id": CAM1_UUID, "node_id": "CAM-01", "device_type": "CAMERA", "farm_id": FARM_1, "zone_id": None, "is_active": True})

    cam = _adapter(ok).resolve_camera(CAM1_UUID, "tok")
    assert (cam.node_id, cam.farm_id) == ("CAM-01", FARM_1)


@pytest.mark.parametrize(
    "status_code,body,exc",
    [
        (200, {"node_id": "SWC-DEMO-NODE-001", "device_type": "ENVIRONMENT_MONITOR", "farm_id": FARM_1}, CameraNotAuthorized),
        (200, {"node_id": "CAM-09", "device_type": "CAMERA", "farm_id": FARM_1, "is_active": False}, CameraNotAuthorized),
        (200, {"device_type": "CAMERA"}, CameraRegistryUnavailable),
        (403, {"detail": "x"}, CameraNotAuthorized),
        (404, {"detail": "x"}, CameraNotAuthorized),
        (400, {"detail": "x"}, CameraNotAuthorized),
        (401, {"detail": "x"}, CameraRegistryUnauthorized),
        (500, {"detail": "x"}, CameraRegistryUnavailable),
    ],
)
def test_adapter_fail_closed_mapping(status_code, body, exc):
    with pytest.raises(exc):
        _adapter(lambda r: httpx.Response(status_code, json=body)).resolve_camera("CAM-01", "tok")


def test_adapter_network_error_is_unavailable():
    def boom(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(CameraRegistryUnavailable):
        _adapter(boom).resolve_camera("CAM-01", "tok")
