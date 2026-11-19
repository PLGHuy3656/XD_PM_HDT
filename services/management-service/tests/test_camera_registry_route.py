"""CP13 hardening R3 — Management GET /api/cameras/{id} must not disclose
other tenants' device ids or any device type.

Pure unit test: repositories/controllers are monkeypatched, no database.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.routes import device_routes

FARM_1 = "a18d8eee-cb1a-4b00-b375-d505eb8128d7"
FARM_2 = "f8fc4fa7-0d27-4e0b-89c0-e676e0e73469"
OWNER_A = {"id": "owner-a", "roles": ["FARM_OWNER"]}
TECH_A = {"id": "tech-a", "roles": ["TECHNICIAN"]}
OWNER_B = {"id": "owner-b", "roles": ["FARM_OWNER"]}
ADMIN = {"id": "admin", "roles": ["ADMIN"]}

DEVICES = {
    "CAM-01": {"device_id": "c0000001-0000-0000-0000-000000000001", "node_id": "CAM-01", "device_type": "CAMERA", "farm_id": FARM_1},
    "c0000001-0000-0000-0000-000000000001": {"device_id": "c0000001-0000-0000-0000-000000000001", "node_id": "CAM-01", "device_type": "CAMERA", "farm_id": FARM_1},
    "CAM-02": {"device_id": "c0000002-0000-0000-0000-000000000002", "node_id": "CAM-02", "device_type": "CAMERA", "farm_id": FARM_2},
    "SWC-DEMO-NODE-001": {"device_id": "d1", "node_id": "SWC-DEMO-NODE-001", "device_type": "ENVIRONMENT_MONITOR", "farm_id": FARM_1},
    "SWC-DEMO-NODE-002": {"device_id": "d2", "node_id": "SWC-DEMO-NODE-002", "device_type": "ENVIRONMENT_MONITOR", "farm_id": FARM_2},
}
OWNED = {"owner-a": {FARM_1}, "owner-b": {FARM_2}}
ASSIGNED = {"tech-a": {FARM_1}}


@pytest.fixture
def client(monkeypatch):
    device_reads: list[str] = []

    monkeypatch.setattr(
        device_routes.user_repository,
        "get_farm_id_for_device",
        lambda device_id: (DEVICES.get(device_id) or {}).get("farm_id"),
    )
    monkeypatch.setattr(
        device_routes.user_repository,
        "is_farm_owned_by_user",
        lambda user_id, farm_id: farm_id in OWNED.get(user_id, set()),
        raising=False,
    )
    monkeypatch.setattr(
        device_routes.user_repository,
        "is_farm_assigned_to_technician",
        lambda user_id, farm_id: farm_id in ASSIGNED.get(user_id, set()),
        raising=False,
    )

    def get_device(device_id):
        device_reads.append(device_id)
        return dict(DEVICES[device_id])

    monkeypatch.setattr(device_routes.device_controller, "get_device", get_device)

    app = FastAPI()
    app.include_router(device_routes.camera_router)
    holder = {"user": OWNER_A}
    app.dependency_overrides[get_current_user] = lambda: holder["user"]
    c = TestClient(app)

    def call(user, camera_id):
        holder["user"] = user
        return c.get(f"/api/cameras/{camera_id}")

    return call, device_reads


def _assert_uniform_not_found(resp):
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Camera not found"}
    assert "ENVIRONMENT_MONITOR" not in resp.text


@pytest.mark.parametrize(
    "user,camera,expected_node",
    [
        (OWNER_A, "CAM-01", "CAM-01"),
        (OWNER_A, "c0000001-0000-0000-0000-000000000001", "CAM-01"),
        (TECH_A, "CAM-01", "CAM-01"),
        (OWNER_B, "CAM-02", "CAM-02"),
        (ADMIN, "CAM-02", "CAM-02"),
    ],
)
def test_authorized_camera_returns_canonical_record(client, user, camera, expected_node):
    call, _ = client
    resp = call(user, camera)
    assert resp.status_code == 200
    assert resp.json()["node_id"] == expected_node
    assert resp.json()["device_type"] == "CAMERA"


@pytest.mark.parametrize(
    "user,camera",
    [
        (OWNER_A, "SWC-DEMO-NODE-001"),  # own sensor
        (ADMIN, "SWC-DEMO-NODE-001"),    # admin + sensor
        (OWNER_A, "NO-SUCH-ID"),         # unknown
        (ADMIN, "CAM-FAKE-999"),         # admin + unregistered
    ],
)
def test_non_camera_or_unknown_is_uniform_404(client, user, camera):
    call, _ = client
    _assert_uniform_not_found(call(user, camera))


@pytest.mark.parametrize(
    "user,camera",
    [
        (OWNER_A, "SWC-DEMO-NODE-002"),  # other tenant's sensor
        (OWNER_A, "CAM-02"),             # other tenant's camera
        (TECH_A, "CAM-02"),
        (OWNER_B, "CAM-01"),
    ],
)
def test_cross_tenant_devices_are_indistinguishable_from_unknown(client, user, camera):
    call, device_reads = client
    resp = call(user, camera)
    _assert_uniform_not_found(resp)
    assert resp.json() == call(user, "NO-SUCH-ID").json()
    # Ownership is checked before any device detail is read.
    assert camera not in device_reads
