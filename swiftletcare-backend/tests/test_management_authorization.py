from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException

from app.services.management_authorization import (
    get_monitorable_device_node_ids,
    require_device_operate_permission,
    require_device_monitor_permission,
)


@patch("app.services.management_authorization.httpx.post")
def test_authorization_sends_node_id_and_accepts_allowed_response(mock_post):
    mock_post.return_value = httpx.Response(
        200,
        json={"allowed": True},
    )

    require_device_operate_permission("node-01", "Bearer test-token")

    args, kwargs = mock_post.call_args
    assert args[0].endswith("/internal/authorization/devices/node-01/operate")
    assert kwargs["headers"] == {"Authorization": "Bearer test-token"}
    assert kwargs["timeout"] == 5.0


@patch("app.services.management_authorization.httpx.post")
def test_authorization_rejects_non_object_response(mock_post):
    mock_post.return_value = httpx.Response(200, json=[])

    with pytest.raises(HTTPException) as exc:
        require_device_operate_permission("node-01", "Bearer test-token")

    assert exc.value.status_code == 503
    assert exc.value.detail == "Invalid authorization service response"


@patch("app.services.management_authorization.httpx.post")
def test_monitor_authorization_uses_monitor_endpoint(mock_post):
    mock_post.return_value = httpx.Response(200, json={"allowed": True})

    require_device_monitor_permission("node-01", "Bearer token")

    assert mock_post.call_args.args[0].endswith(
        "/internal/authorization/devices/node-01/monitor",
    )


@patch("app.services.management_authorization.httpx.get")
def test_list_monitorable_devices_returns_only_node_ids(mock_get):
    mock_get.return_value = httpx.Response(
        200,
        json=[
            {"node_id": "node-01"},
            {"node_id": "node-02"},
        ],
    )

    assert get_monitorable_device_node_ids("Bearer token") == {
        "node-01",
        "node-02",
    }

    assert mock_get.call_args.kwargs["headers"] == {
        "Authorization": "Bearer token",
    }


@patch("app.services.management_authorization.httpx.get")
def test_list_monitorable_devices_rejects_invalid_response(mock_get):
    mock_get.return_value = httpx.Response(
        200,
        json=[{"device_id": "uuid-without-node-id"}],
    )

    with pytest.raises(HTTPException) as exc:
        get_monitorable_device_node_ids("Bearer token")

    assert exc.value.status_code == 503
