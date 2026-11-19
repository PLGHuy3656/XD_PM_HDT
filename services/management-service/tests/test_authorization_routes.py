from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.repositories.user_repository import user_repository
from app.routes.authorization_routes import (
    authorize_device_monitoring,
    authorize_device_operation,
    get_analytics_device_context,
    list_analytics_device_contexts,
)
from app.repositories.device_repository import device_repository


def test_admin_can_operate_device_resolved_by_node_id(monkeypatch):
    resolved_ids = []

    def resolve_device(device_id):
        resolved_ids.append(device_id)
        return "farm-01"

    monkeypatch.setattr(
        user_repository,
        "get_farm_id_for_device",
        resolve_device,
    )

    result = authorize_device_operation(
        "node-01",
        current_user={"id": "admin-01", "roles": ["ADMIN"]},
    )

    assert result == {"allowed": True}
    assert resolved_ids == ["node-01"]


def test_technician_with_operate_permission_is_allowed(monkeypatch):
    monkeypatch.setattr(
        user_repository,
        "get_farm_id_for_device",
        lambda device_id: "farm-01",
    )
    permission_checks = []

    def check_permission(technician_id, farm_id, required_permission):
        permission_checks.append(
            (technician_id, farm_id, required_permission),
        )
        return required_permission == "OPERATE"

    monkeypatch.setattr(
        "app.routes.authorization_routes.check_technician_permission",
        check_permission,
    )

    result = authorize_device_operation(
        "node-01",
        current_user={"id": "tech-01", "roles": ["TECHNICIAN"]},
    )

    assert result == {"allowed": True}
    assert permission_checks == [("tech-01", "farm-01", "OPERATE")]


def test_technician_with_monitor_permission_is_forbidden(monkeypatch):
    monkeypatch.setattr(
        user_repository,
        "get_farm_id_for_device",
        lambda device_id: "farm-01",
    )
    monkeypatch.setattr(
        "app.routes.authorization_routes.check_technician_permission",
        lambda technician_id, farm_id, required_permission: False,
    )

    with pytest.raises(HTTPException) as exc:
        authorize_device_operation(
            "node-01",
            current_user={"id": "tech-01", "roles": ["TECHNICIAN"]},
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "OPERATE permission required"


def test_non_technician_non_admin_is_forbidden(monkeypatch):
    monkeypatch.setattr(
        user_repository,
        "get_farm_id_for_device",
        lambda device_id: "farm-01",
    )

    with pytest.raises(HTTPException) as exc:
        authorize_device_operation(
            "node-01",
            current_user={"id": "owner-01", "roles": ["FARM_OWNER"]},
        )

    assert exc.value.status_code == 403


def test_unknown_device_is_not_found(monkeypatch):
    monkeypatch.setattr(
        user_repository,
        "get_farm_id_for_device",
        lambda device_id: None,
    )

    with pytest.raises(HTTPException) as exc:
        authorize_device_operation(
            "unknown-node",
            current_user={"id": "admin-01", "roles": ["ADMIN"]},
        )

    assert exc.value.status_code == 404


def test_farm_owner_can_monitor_owned_device(monkeypatch):
    monkeypatch.setattr(
        user_repository,
        "get_farm_id_for_device",
        lambda device_id: "farm-01",
    )
    access_checks = []

    def verify_access(user, farm_id):
        access_checks.append((user["id"], farm_id))
        return True

    monkeypatch.setattr(
        "app.routes.authorization_routes.verify_farm_resource_access",
        verify_access,
    )

    result = authorize_device_monitoring(
        "node-01",
        current_user={"id": "owner-01", "roles": ["FARM_OWNER"]},
    )

    assert result == {"allowed": True}
    assert access_checks == [("owner-01", "farm-01")]


def test_technician_monitor_access_uses_farm_access_rules(monkeypatch):
    monkeypatch.setattr(
        user_repository,
        "get_farm_id_for_device",
        lambda device_id: "farm-01",
    )
    def deny_access(user, farm_id):
        raise HTTPException(status_code=403)

    monkeypatch.setattr(
        "app.routes.authorization_routes.verify_farm_resource_access",
        deny_access,
    )

    with pytest.raises(HTTPException) as exc:
        authorize_device_monitoring(
            "node-01",
            current_user={"id": "tech-01", "roles": ["TECHNICIAN"]},
        )

    assert exc.value.status_code == 403


def test_internal_analytics_contexts_requires_shared_service_token(
    monkeypatch,
):
    contexts = [{"node_id": "node-01", "recipient_user_ids": ["owner-01"]}]
    monkeypatch.setattr(
        "app.routes.authorization_routes.settings.analytics_service_token",
        "service-secret",
    )
    monkeypatch.setattr(
        device_repository,
        "list_analytics_device_contexts",
        lambda: contexts,
    )

    assert list_analytics_device_contexts("service-secret") == contexts

    with pytest.raises(HTTPException) as exc:
        list_analytics_device_contexts("invalid")
    assert exc.value.status_code == 401


def test_internal_analytics_context_resolves_node_with_farm_and_zone(
    monkeypatch,
):
    context = {
        "node_id": "CAM-01",
        "farm_id": "farm-01",
        "zone_id": "zone-01",
    }
    monkeypatch.setattr(
        "app.routes.authorization_routes.settings.analytics_service_token",
        "service-secret",
    )
    monkeypatch.setattr(
        device_repository,
        "list_analytics_device_contexts",
        lambda node_id: [context] if node_id == "CAM-01" else [],
    )

    assert get_analytics_device_context("CAM-01", "service-secret") == context

    with pytest.raises(HTTPException) as exc:
        get_analytics_device_context("missing", "service-secret")
    assert exc.value.status_code == 404


def test_analytics_device_context_repository_maps_farm_zone_and_recipients():
    device_id = UUID("00000000-0000-4000-8000-000000000001")
    farm_id = UUID("00000000-0000-4000-8000-000000000002")
    zone_id = UUID("00000000-0000-4000-8000-000000000003")
    owner_id = UUID("00000000-0000-4000-8000-000000000004")
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        (
            device_id,
            "CAM-01",
            farm_id,
            "FARM-01",
            "Farm One",
            zone_id,
            "ZONE-01",
            "Zone One",
            [owner_id],
        ),
    ]
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    with patch(
        "app.repositories.device_repository.get_connection",
        return_value=connection_context,
    ):
        contexts = device_repository.list_analytics_device_contexts("CAM-01")

    assert contexts == [
        {
            "device_id": str(device_id),
            "node_id": "CAM-01",
            "farm_id": str(farm_id),
            "farm_code": "FARM-01",
            "farm_name": "Farm One",
            "zone_id": str(zone_id),
            "zone_code": "ZONE-01",
            "zone_name": "Zone One",
            "recipient_user_ids": [str(owner_id)],
        },
    ]
    assert cursor.execute.call_args.args[1] == ("CAM-01",)
