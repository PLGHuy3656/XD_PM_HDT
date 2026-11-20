from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.repositories.device_repository import DeviceRepository
from app.repositories.technician_installation_repository import (
    InstallationStateError,
    TechnicianInstallationRepository,
)
from app.routes import technician_installation_routes as routes
from app.schemas.technician_installation import (
    TechnicianInstallationConfigurationRequest,
    TechnicianInstallationCreateRequest,
)


TECHNICIAN_ID = UUID("00000000-0000-4000-8000-000000000001")
FARM_ID = UUID("00000000-0000-4000-8000-000000000002")
ZONE_ID = UUID("00000000-0000-4000-8000-000000000003")
INSTALLATION_ID = UUID("00000000-0000-4000-8000-000000000004")
DEVICE_ID = UUID("00000000-0000-4000-8000-000000000005")


def _installation_row(
    *,
    status="REGISTERED",
    is_active=False,
    configuration=None,
    validation_report=None,
):
    now = datetime.now(timezone.utc)
    return (
        INSTALLATION_ID,
        DEVICE_ID,
        "NODE-01",
        TECHNICIAN_ID,
        FARM_ID,
        ZONE_ID,
        "Camera 1",
        "CAMERA",
        None,
        None,
        is_active,
        status,
        configuration or {},
        validation_report or {},
        now,
        now,
        None,
        None,
        None,
        True,
    )


def _installation_response(
    *,
    status="ACTIVATED",
    is_active=True,
    configuration=None,
    validation_report=None,
):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "installation_id": INSTALLATION_ID,
        "device_id": DEVICE_ID,
        "node_id": "NODE-01",
        "technician_id": TECHNICIAN_ID,
        "farm_id": FARM_ID,
        "zone_id": ZONE_ID,
        "name": "Camera 1",
        "device_type": "CAMERA",
        "firmware_version": None,
        "ip_address": None,
        "is_active": is_active,
        "status": status,
        "configuration": configuration or {},
        "validation_report": validation_report or {},
        "farm_zone_linked": True,
        "created_at": now,
        "updated_at": now,
        "activated_at": now if is_active else None,
        "validated_at": None,
        "handed_over_at": None,
    }


def test_installation_routes_reject_non_technicians():
    with pytest.raises(HTTPException) as exc:
        routes._require_technician(
            {"id": str(TECHNICIAN_ID), "roles": ["FARM_OWNER"]},
        )

    assert exc.value.status_code == 403


def test_installation_configuration_must_be_non_empty():
    with pytest.raises(ValueError):
        TechnicianInstallationConfigurationRequest(configuration={})


@patch(
    "app.routes.technician_installation_routes.technician_installation_repository.create_installation",
    return_value={"installation_id": INSTALLATION_ID},
)
@patch(
    "app.routes.technician_installation_routes.user_repository.get_farm_id_for_zone",
    return_value=str(FARM_ID),
)
@patch(
    "app.routes.technician_installation_routes.user_repository.is_farm_assigned_to_technician",
    return_value=True,
)
def test_register_installation_requires_assigned_farm_and_matching_zone(
    _assignment,
    _zone_farm,
    create,
):
    payload = TechnicianInstallationCreateRequest(
        node_id="NODE-01",
        farm_id=FARM_ID,
        zone_id=ZONE_ID,
        name="Camera 1",
        device_type="CAMERA",
    )

    result = routes.register_installation(
        payload,
        {"id": str(TECHNICIAN_ID), "roles": ["TECHNICIAN"]},
    )

    assert result["installation_id"] == INSTALLATION_ID
    create.assert_called_once_with(
        technician_id=TECHNICIAN_ID,
        node_id="NODE-01",
        farm_id=FARM_ID,
        zone_id=ZONE_ID,
        name="Camera 1",
        device_type="CAMERA",
        firmware_version=None,
        ip_address=None,
    )


@patch(
    "app.routes.technician_installation_routes.technician_installation_repository.create_installation",
)
@patch(
    "app.routes.technician_installation_routes.user_repository.is_farm_assigned_to_technician",
    return_value=False,
)
def test_register_installation_rejects_unassigned_farm(
    _assignment,
    create,
):
    payload = TechnicianInstallationCreateRequest(
        node_id="NODE-01",
        farm_id=FARM_ID,
    )

    with pytest.raises(HTTPException) as exc:
        routes.register_installation(
            payload,
            {"id": str(TECHNICIAN_ID), "roles": ["TECHNICIAN"]},
        )

    assert exc.value.status_code == 403
    create.assert_not_called()


@patch(
    "app.routes.technician_installation_routes.technician_installation_repository.create_installation",
)
@patch(
    "app.routes.technician_installation_routes.user_repository.get_farm_id_for_zone",
    return_value="00000000-0000-4000-8000-000000000099",
)
@patch(
    "app.routes.technician_installation_routes.user_repository.is_farm_assigned_to_technician",
    return_value=True,
)
def test_register_installation_rejects_zone_from_different_farm(
    _assignment,
    _zone_farm,
    create,
):
    payload = TechnicianInstallationCreateRequest(
        node_id="NODE-01",
        farm_id=FARM_ID,
        zone_id=ZONE_ID,
    )

    with pytest.raises(HTTPException) as exc:
        routes.register_installation(
            payload,
            {"id": str(TECHNICIAN_ID), "roles": ["TECHNICIAN"]},
        )

    assert exc.value.status_code == 400
    create.assert_not_called()


def test_validation_records_failed_connectivity_and_does_not_pass_handover():
    installation = _installation_response(
        configuration={"sensors": ["temperature"]},
    )
    saved = _installation_response(
        configuration={"sensors": ["temperature"]},
        validation_report={"passed": False},
    )
    with (
        patch.object(routes, "_get_installation_or_404", return_value=installation),
        patch.object(
            routes.legacy_iot_adapter,
            "get_devices_runtime_state",
            return_value={},
        ),
        patch.object(
            routes.technician_installation_repository,
            "save_validation_report",
            return_value=saved,
        ) as save_report,
    ):
        result = routes.validate_installation(
            INSTALLATION_ID,
            {"id": str(TECHNICIAN_ID), "roles": ["TECHNICIAN"]},
        )

    assert result.passed is False
    assert result.checks.connectivity is False
    assert result.failure_reasons == ["connectivity"]
    assert save_report.call_args.kwargs["passed"] is False


def test_validation_passes_when_device_is_connected_and_persists_result():
    installation = _installation_response(
        configuration={"sensors": ["temperature"]},
    )
    saved = _installation_response(
        status="VALIDATED",
        configuration={"sensors": ["temperature"]},
        validation_report={"passed": True},
    )
    with (
        patch.object(routes, "_get_installation_or_404", return_value=installation),
        patch.object(
            routes.legacy_iot_adapter,
            "get_devices_runtime_state",
            return_value={str(DEVICE_ID): {"recorded_at": datetime.now(timezone.utc)}},
        ),
        patch.object(
            routes.technician_installation_repository,
            "save_validation_report",
            return_value=saved,
        ) as save_report,
    ):
        result = routes.validate_installation(
            INSTALLATION_ID,
            {"id": str(TECHNICIAN_ID), "roles": ["TECHNICIAN"]},
        )

    assert result.passed is True
    assert result.checks.connectivity is True
    assert result.failure_reasons == []
    assert save_report.call_args.kwargs["passed"] is True


def test_activation_requires_configuration_and_sets_registry_active():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (uuid4(),),
        ("CONFIGURED", {"sensors": ["temperature"]}, False, DEVICE_ID),
        _installation_row(
            status="ACTIVATED",
            is_active=True,
            configuration={"sensors": ["temperature"]},
        ),
    ]
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    with patch(
        "app.repositories.technician_installation_repository.get_connection",
        return_value=connection_context,
    ):
        result = TechnicianInstallationRepository().activate_installation(
            INSTALLATION_ID,
            TECHNICIAN_ID,
        )

    assert result["status"] == "ACTIVATED"
    assert result["is_active"] is True
    executed_queries = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("SET is_active = TRUE" in query for query in executed_queries)
    assert any("SET status = 'ACTIVATED'" in query for query in executed_queries)


def test_handover_is_rejected_until_validation_passes():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (uuid4(),),
        ("ACTIVATED", {"sensors": ["temperature"]}, True, DEVICE_ID),
    ]
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    with patch(
        "app.repositories.technician_installation_repository.get_connection",
        return_value=connection_context,
    ):
        with pytest.raises(InstallationStateError, match="pass validation"):
            TechnicianInstallationRepository().hand_over_installation(
                INSTALLATION_ID,
                TECHNICIAN_ID,
            )

    assert cursor.execute.call_count == 2


def test_handover_records_completion_after_validation():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (uuid4(),),
        ("VALIDATED", {"sensors": ["temperature"]}, True, DEVICE_ID),
        _installation_row(
            status="HANDED_OVER",
            is_active=True,
            configuration={"sensors": ["temperature"]},
        ),
    ]
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    with patch(
        "app.repositories.technician_installation_repository.get_connection",
        return_value=connection_context,
    ):
        result = TechnicianInstallationRepository().hand_over_installation(
            INSTALLATION_ID,
            TECHNICIAN_ID,
        )

    assert result["status"] == "HANDED_OVER"
    assert any(
        "SET status = 'HANDED_OVER'" in call.args[0]
        for call in cursor.execute.call_args_list
    )


def test_registration_creates_inactive_device_and_installation_atomically():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (uuid4(),),
        (DEVICE_ID,),
        (INSTALLATION_ID,),
        _installation_row(),
    ]
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    with patch(
        "app.repositories.technician_installation_repository.get_connection",
        return_value=connection_context,
    ):
        result = TechnicianInstallationRepository().create_installation(
            technician_id=TECHNICIAN_ID,
            node_id="NODE-01",
            farm_id=FARM_ID,
            zone_id=ZONE_ID,
            name="Camera 1",
            device_type="CAMERA",
            firmware_version=None,
            ip_address=None,
        )

    assert result["status"] == "REGISTERED"
    assert result["is_active"] is False
    create_device_query = cursor.execute.call_args_list[1].args[0]
    assert "FALSE" in create_device_query
    assert "technician_assignments" in create_device_query
    assert "INSERT INTO technician_installations" in (
        cursor.execute.call_args_list[2].args[0]
    )


def test_zone_changes_keep_open_installation_location_in_sync():
    cursor = MagicMock()
    cursor.fetchone.return_value = (DEVICE_ID,)
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    with patch(
        "app.repositories.device_repository.get_connection",
        return_value=connection_context,
    ):
        updated = DeviceRepository().update_device_zone(
            "NODE-01",
            str(FARM_ID),
            str(ZONE_ID),
        )

    assert updated is True
    query = cursor.execute.call_args.args[0]
    assert "UPDATE technician_installations AS installation" in query
    assert "installation.status <> 'HANDED_OVER'" in query
