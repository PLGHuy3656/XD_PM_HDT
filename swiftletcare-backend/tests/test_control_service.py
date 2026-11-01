import pytest
from unittest.mock import patch, MagicMock
from uuid import UUID

from fastapi import HTTPException

from app.routes import control_router
from app.schemas.control import (
    RelayCommandRequest,
    ThresholdCommandRequest,
)
from app.services.control_service import (
    prepare_relay_command,
    prepare_threshold_command,
)


@patch("app.services.control_service.create_command")
def test_prepare_relay_command(mock_create_command):
    mock_create_command.return_value = {
        "status": "PENDING",
        "action": "SET_RELAY",
    }

    request = RelayCommandRequest(
        action="SET_RELAY",
        target="fan",
        state=1,
    )

    result = prepare_relay_command(
        device_id="23e215eb-9036-4417-8de3-dcbcdf5757fa",
        request=request,
    )

    assert result["command"]["action"] == "SET_RELAY"
    assert result["command"]["target"] == "fan"
    assert result["command"]["state"] == 1
    assert result["command"]["commandId"]
    mock_create_command.assert_called_once()


@patch("app.services.control_service.create_command")
def test_prepare_threshold_command(mock_create_command):
    mock_create_command.return_value = {
        "status": "PENDING",
        "action": "UPDATE_THRESHOLDS",
    }

    request = ThresholdCommandRequest(
        action="UPDATE_THRESHOLDS",
        targetTemp=25,
        targetHum=70,
    )

    result = prepare_threshold_command(
        device_id="23e215eb-9036-4417-8de3-dcbcdf5757fa",
        request=request,
    )

    assert result["command"]["action"] == "UPDATE_THRESHOLDS"
    assert result["command"]["targetTemp"] == 25
    assert result["command"]["targetHum"] == 70
    assert result["command"]["commandId"]
    mock_create_command.assert_called_once()


from unittest.mock import MagicMock

from app.mqtt.control import publish_command


@patch("app.mqtt.control.mqtt.Client")
def test_publish_command_when_connected(mock_client_class):
    client = MagicMock()
    client.is_connected.return_value = True
    client.publish.return_value.rc = 0

    payload = {
        "commandId": "test-command-001",
        "action": "SET_RELAY",
        "target": "fan",
        "state": 1,
    }

    publish_command(client, "device01", payload)

    client.publish.assert_called_once()
    args, kwargs = client.publish.call_args
    assert args[0] == "swiftlet/command/device01"
    assert kwargs["qos"] == 1
    assert kwargs["retain"] is False


def test_publish_command_when_disconnected():
    client = MagicMock()
    client.is_connected.return_value = False

    payload = {
        "commandId": "test-command-002",
        "action": "SET_RELAY",
        "target": "fan",
        "state": 1,
    }

    with pytest.raises(RuntimeError, match="not connected"):
        publish_command(client, "device01", payload)

    client.publish.assert_not_called()


from app.services.control_service import send_prepared_command


@patch("app.services.control_service.get_active_device_node_id")
@patch("app.services.control_service.publish_command")
@patch("app.services.control_service.mark_command_sent")
def test_send_prepared_command_success(
    mock_mark_sent,
    mock_publish,
    mock_get_node,
):
    mock_get_node.return_value = "device01"
    mock_mark_sent.return_value = True

    prepared = {
        "command": {
            "commandId": "test-command-003",
            "action": "SET_RELAY",
            "target": "fan",
            "state": 1,
        },
        "record": {
            "status": "PENDING",
        },
    }

    client = MagicMock()

    result = send_prepared_command(
        device_id="23e215eb-9036-4417-8de3-dcbcdf5757fa",
        prepared=prepared,
        mqtt_client=client,
    )

    mock_publish.assert_called_once_with(
        client,
        "device01",
        prepared["command"],
    )
    mock_mark_sent.assert_called_once_with("test-command-003")
    assert result["sent"] is True
    assert result["nodeId"] == "device01"


@patch("app.services.control_service.get_active_device_node_id")
@patch("app.services.control_service.publish_command")
def test_send_prepared_command_when_device_inactive(
    mock_publish,
    mock_get_node,
):
    mock_get_node.return_value = None

    prepared = {
        "command": {
            "commandId": "test-command-004",
            "action": "SET_RELAY",
            "target": "fan",
            "state": 1,
        },
        "record": {"status": "PENDING"},
    }

    with pytest.raises(ValueError, match="Active device not found"):
        send_prepared_command(
            device_id="23e215eb-9036-4417-8de3-dcbcdf5757fa",
            prepared=prepared,
            mqtt_client=MagicMock(),
        )

    mock_publish.assert_not_called()


@patch("app.services.control_service.get_active_device_node_id")
@patch("app.services.control_service.mark_command_failed")
@patch("app.services.control_service.publish_command")
def test_send_prepared_command_when_publish_fails(
    mock_publish,
    mock_mark_failed,
    mock_get_node,
):
    mock_get_node.return_value = "device01"
    mock_publish.side_effect = RuntimeError("MQTT client is not connected")

    prepared = {
        "command": {
            "commandId": "test-command-005",
            "action": "SET_RELAY",
            "target": "fan",
            "state": 1,
        },
        "record": {"status": "PENDING"},
    }

    with pytest.raises(RuntimeError, match="not connected"):
        send_prepared_command(
            device_id="23e215eb-9036-4417-8de3-dcbcdf5757fa",
            prepared=prepared,
            mqtt_client=MagicMock(),
        )

    mock_mark_failed.assert_called_once_with(
        "test-command-005",
        "MQTT client is not connected",
    )


@patch("app.services.control_service.get_active_device_node_id")
def test_get_control_device_node_id(mock_get_node):
    from app.services.control_service import get_control_device_node_id

    device_id = UUID("23e215eb-9036-4417-8de3-dcbcdf5757fa")
    mock_get_node.return_value = "device01"

    assert get_control_device_node_id(device_id) == "device01"
    mock_get_node.assert_called_once_with(device_id)


def test_send_control_command_authorizes_by_node_id():
    device_id = UUID("23e215eb-9036-4417-8de3-dcbcdf5757fa")
    request = MagicMock()
    request.app.state.mqtt_client = MagicMock()
    body = RelayCommandRequest(
        action="SET_RELAY",
        target="fan",
        state=1,
    )
    prepared = {"command": {"commandId": "command-001"}}
    sent = {"sent": True}

    with (
        patch.object(
            control_router,
            "get_control_device_node_id",
            return_value="device01",
        ) as get_node,
        patch.object(
            control_router,
            "require_device_operate_permission",
        ) as authorize,
        patch.object(
            control_router,
            "prepare_relay_command",
            return_value=prepared,
        ) as prepare,
        patch.object(
            control_router,
            "send_prepared_command",
            return_value=sent,
        ) as send,
    ):
        result = control_router.send_control_command(
            device_id,
            body,
            request,
            "Bearer test-token",
        )

    assert result == sent
    get_node.assert_called_once_with(device_id)
    authorize.assert_called_once_with("device01", "Bearer test-token")
    prepare.assert_called_once_with(device_id, body)
    send.assert_called_once_with(
        device_id,
        prepared,
        request.app.state.mqtt_client,
    )


def test_send_control_command_rejects_inactive_device_before_authorizing():
    device_id = UUID("23e215eb-9036-4417-8de3-dcbcdf5757fa")
    request = MagicMock()
    body = RelayCommandRequest(
        action="SET_RELAY",
        target="fan",
        state=1,
    )

    with (
        patch.object(
            control_router,
            "get_control_device_node_id",
            return_value=None,
        ),
        patch.object(
            control_router,
            "require_device_operate_permission",
        ) as authorize,
        patch.object(
            control_router,
            "prepare_relay_command",
        ) as prepare,
    ):
        with pytest.raises(HTTPException) as exc:
            control_router.send_control_command(
                device_id,
                body,
                request,
                "Bearer test-token",
            )

    assert exc.value.status_code == 404
    authorize.assert_not_called()
    prepare.assert_not_called()


def test_send_control_command_does_not_prepare_command_when_forbidden():
    device_id = UUID("23e215eb-9036-4417-8de3-dcbcdf5757fa")
    request = MagicMock()
    body = RelayCommandRequest(
        action="SET_RELAY",
        target="fan",
        state=1,
    )

    with (
        patch.object(
            control_router,
            "get_control_device_node_id",
            return_value="device01",
        ),
        patch.object(
            control_router,
            "require_device_operate_permission",
            side_effect=HTTPException(status_code=403),
        ),
        patch.object(
            control_router,
            "prepare_relay_command",
        ) as prepare,
        patch.object(
            control_router,
            "send_prepared_command",
        ) as send,
    ):
        with pytest.raises(HTTPException) as exc:
            control_router.send_control_command(
                device_id,
                body,
                request,
                "Bearer test-token",
            )

    assert exc.value.status_code == 403
    prepare.assert_not_called()
    send.assert_not_called()


def test_get_control_state_requires_monitor_permission():
    device_id = UUID("23e215eb-9036-4417-8de3-dcbcdf5757fa")
    state = {"deviceId": str(device_id)}

    with (
        patch.object(
            control_router,
            "get_control_device_node_id",
            return_value="device01",
        ),
        patch.object(
            control_router,
            "require_device_monitor_permission",
        ) as authorize,
        patch.object(
            control_router,
            "fetch_control_state",
            return_value=state,
        ) as fetch,
    ):
        result = control_router.get_control_state(
            device_id,
            "Bearer test-token",
        )

    assert result == state
    authorize.assert_called_once_with("device01", "Bearer test-token")
    fetch.assert_called_once_with(device_id)


def test_get_control_commands_checks_permission_before_reading_commands():
    device_id = UUID("23e215eb-9036-4417-8de3-dcbcdf5757fa")

    with (
        patch.object(
            control_router,
            "get_control_device_node_id",
            return_value="device01",
        ),
        patch.object(
            control_router,
            "require_device_monitor_permission",
            side_effect=HTTPException(status_code=403),
        ),
        patch.object(control_router, "fetch_control_commands") as fetch,
    ):
        with pytest.raises(HTTPException) as exc:
            control_router.get_control_commands(
                device_id,
                authorization="Bearer test-token",
            )

    assert exc.value.status_code == 403
    fetch.assert_not_called()
