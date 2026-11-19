from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.ai_events import event_fingerprint, store_ai_event
from app.main import app
from app.reports import telemetry_csv, telemetry_pdf
from app.repository import (
    get_ai_event_by_id,
    get_ai_events,
    save_ai_event,
    save_bird_track_points,
)
from app.routes import _authorized_farm_ids
from app.services import get_bird_analytics_data
from app.schemas import (
    AIAudioEventRequest,
    AICountSnapshotRequest,
    AIDetectionBatchRequest,
    AIVisionEventRequest,
)


def test_ai_event_list_repository_applies_filters_and_stable_pagination():
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection
    start = datetime(2026, 11, 18, tzinfo=timezone.utc)
    end = datetime(2026, 11, 19, tzinfo=timezone.utc)

    with patch(
        "app.repository.get_connection",
        return_value=connection_context,
    ):
        result = get_ai_events(
            ["CAM-01", "CAM-02"],
            start,
            end,
            source_type="vision",
            event_type="PREDATOR_DETECTED",
            camera_id="CAM-02",
            limit=25,
            offset=50,
        )

    query, params = cursor.execute.call_args.args
    assert result == []
    assert "event_type = %s" in query
    assert "camera_id = %s" in query
    assert "ORDER BY observed_at DESC, id DESC LIMIT %s OFFSET %s" in query
    assert params == (
        ["CAM-01", "CAM-02"],
        start,
        end,
        "vision",
        "PREDATOR_DETECTED",
        "CAM-02",
        25,
        50,
    )


def test_ai_event_detail_repository_scopes_id_to_authorized_camera_ids():
    event_id = UUID("00000000-0000-4000-8000-000000000012")
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    with patch(
        "app.repository.get_connection",
        return_value=connection_context,
    ):
        result = get_ai_event_by_id(["CAM-01"], event_id)

    query, params = cursor.execute.call_args.args
    assert result is None
    assert "id = %s" in query
    assert "camera_id = ANY(%s)" in query
    assert params == (event_id, ["CAM-01"])


def test_ai_event_duplicate_does_not_create_notification_outbox_row():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    with patch(
        "app.repository.get_connection",
        return_value=connection_context,
    ):
        result = save_ai_event(
            event_key="a" * 64,
            source_event_id=None,
            source_type="audio",
            camera_id="CAM-01",
            event_type="AUDIO_ANOMALY",
            label="predator_sound",
            confidence=0.9,
            observed_at=datetime.now(timezone.utc),
            context={
                "farm_id": "00000000-0000-4000-8000-000000000001",
                "farm_code": "FARM-01",
                "farm_name": "Farm One",
                "zone_id": None,
            },
            payload={"cameraId": "CAM-01"},
            notification_event={
                "event_id": "00000000-0000-4000-8000-000000000002",
                "event_type": "audio.anomaly.detected",
            },
        )

    assert result is None
    assert cursor.execute.call_count == 1


def test_new_ai_event_and_notification_outbox_are_saved_together():
    event_id = UUID("00000000-0000-4000-8000-000000000003")
    cursor = MagicMock()
    cursor.fetchone.return_value = (event_id,)
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    with patch(
        "app.repository.get_connection",
        return_value=connection_context,
    ):
        result = save_ai_event(
            event_key="b" * 64,
            source_event_id=None,
            source_type="vision",
            camera_id="CAM-01",
            event_type="PREDATOR_DETECTED",
            label="snake",
            confidence=0.91,
            observed_at=datetime.now(timezone.utc),
            context={
                "farm_id": "00000000-0000-4000-8000-000000000001",
                "farm_code": "FARM-01",
                "farm_name": "Farm One",
                "zone_id": "00000000-0000-4000-8000-000000000004",
                "zone_code": "ZONE-01",
                "zone_name": "Zone One",
            },
            payload={"cameraId": "CAM-01"},
            notification_event={
                "event_id": "00000000-0000-4000-8000-000000000005",
                "event_type": "ai.threat.detected",
            },
        )

    assert result == event_id
    assert cursor.execute.call_count == 2
    assert "INSERT INTO public.analytics_event_outbox" in (
        cursor.execute.call_args.args[0]
    )


def test_ai_event_fingerprint_is_stable_for_ids_and_canonical_payloads():
    event_id = UUID("00000000-0000-4000-8000-000000000006")

    assert event_fingerprint(
        "vision",
        event_id,
        {"class": "snake"},
    ) == event_fingerprint(
        "vision",
        event_id,
        {"class": "different-payload"},
    )
    assert event_fingerprint(
        "audio",
        None,
        {"label": "sound", "timestamp": 1728135000},
    ) == event_fingerprint(
        "audio",
        None,
        {"timestamp": 1728135000, "label": "sound"},
    )


def test_detection_batch_accepts_tracked_bird_positions():
    batch = AIDetectionBatchRequest.model_validate(
        {
            "cameraId": "CAM-01",
            "timestamp": 1728135000,
            "detections": [
                {
                    "class": "swiftlet",
                    "confidence": 0.94,
                    "trackId": 21,
                    "bbox": [120, 80, 165, 140],
                },
            ],
        },
    )

    assert batch.detections[0].track_id == 21
    assert batch.detections[0].bbox == (120, 80, 165, 140)

    with pytest.raises(ValueError):
        AIDetectionBatchRequest.model_validate(
            {
                "cameraId": "CAM-01",
                "timestamp": 1728135000,
                "detections": [
                    {
                        "class": "swiftlet",
                        "confidence": 0.94,
                        "trackId": 21,
                        "bbox": [120, 80, 100, 140],
                    },
                ],
            },
        )


@patch(
    "app.ai_events.save_ai_event",
    return_value=UUID("00000000-0000-4000-8000-000000000007"),
)
def test_vision_event_maps_location_and_threat_to_notification(mock_save):
    observed_at = int(datetime.now(timezone.utc).timestamp())
    event = AIVisionEventRequest.model_validate(
        {
            "eventId": "00000000-0000-4000-8000-000000000008",
            "cameraId": "CAM-01",
            "eventType": "PREDATOR_DETECTED",
            "class": "snake",
            "confidence": 0.9,
            "timestamp": observed_at,
            "bbox": [1, 2, 20, 30],
        },
    )
    context = {
        "node_id": "CAM-01",
        "farm_id": "00000000-0000-4000-8000-000000000001",
        "farm_code": "FARM-01",
        "farm_name": "Farm One",
        "zone_id": "00000000-0000-4000-8000-000000000002",
        "zone_code": "ZONE-01",
        "zone_name": "Zone One",
        "recipient_user_ids": [
            "00000000-0000-4000-8000-000000000003",
        ],
    }

    assert store_ai_event("vision", event, context) == UUID(
        "00000000-0000-4000-8000-000000000007",
    )
    saved = mock_save.call_args.kwargs
    assert saved["source_event_id"] == event.event_id
    assert saved["label"] == "snake"
    assert saved["notification_event"]["event_type"] == "ai.threat.detected"
    assert saved["notification_event"]["recipient_user_ids"] == (
        context["recipient_user_ids"]
    )
    assert saved["notification_event"]["data"]["farm_id"] == context["farm_id"]
    assert saved["notification_event"]["data"]["bbox"] == [1, 2, 20, 30]


@patch(
    "app.ai_events.save_ai_event",
    return_value=UUID("00000000-0000-4000-8000-000000000009"),
)
def test_audio_event_maps_measurements_to_notification(mock_save):
    event = AIAudioEventRequest.model_validate(
        {
            "cameraId": "CAM-01",
            "eventType": "AUDIO_ANOMALY",
            "label": "predator_sound",
            "confidence": 0.88,
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "audioRms": 0.72,
            "threshold": 0.5,
        },
    )
    context = {
        "node_id": "CAM-01",
        "farm_id": "00000000-0000-4000-8000-000000000001",
        "farm_code": "FARM-01",
        "farm_name": "Farm One",
        "zone_id": None,
        "recipient_user_ids": [
            "00000000-0000-4000-8000-000000000003",
        ],
    }

    store_ai_event("audio", event, context)

    saved = mock_save.call_args.kwargs
    assert saved["source_type"] == "audio"
    assert saved["label"] == "predator_sound"
    assert saved["notification_event"]["event_type"] == (
        "audio.anomaly.detected"
    )
    assert saved["notification_event"]["data"]["audio_rms"] == 0.72
    assert saved["notification_event"]["data"]["threshold"] == 0.5


def _telemetry_result():
    statistics = {"average": 25.0, "minimum": 24.0, "maximum": 26.0}
    return {
        "period": "24h",
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-02T00:00:00+00:00",
        "device_count": 1,
        "sample_count": 2,
        "summary": {
            metric: statistics
            for metric in (
                "temperature",
                "humidity",
                "co2",
                "lux",
                "audio_rms",
            )
        },
        "series": [],
    }


def test_ai_count_contract_requires_matching_net_change():
    payload = AICountSnapshotRequest.model_validate(
        {
            "cameraId": "CAM-01",
            "timestamp": 1728135000,
            "entryCount": 125,
            "exitCount": 98,
            "netChange": 27,
        },
    )

    assert payload.net_change == 27
    with pytest.raises(ValueError, match="netChange"):
        AICountSnapshotRequest.model_validate(
            {
                "cameraId": "CAM-01",
                "timestamp": 1728135000,
                "entryCount": 125,
                "exitCount": 98,
                "netChange": 26,
            },
        )


@patch("app.routes.save_ai_count_snapshot", return_value=True)
@patch(
    "app.routes.get_analytics_device_context",
    return_value={"node_id": "CAM-01"},
)
@patch("app.routes.settings.ai_ingest_token", "secret-token")
def test_ai_counts_endpoint_authenticates_and_stores_contract_payload(
    _mock_context,
    mock_save,
):
    with TestClient(app) as client:
        response = client.post(
            "/api/ai/counts",
            headers={"X-AI-Ingest-Token": "secret-token"},
            json={
                "cameraId": "CAM-01",
                "timestamp": int(datetime.now(timezone.utc).timestamp()),
                "entryCount": 125,
                "exitCount": 98,
                "netChange": 27,
            },
        )

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "duplicate": False}
    assert mock_save.call_args.args[0] == "CAM-01"
    assert mock_save.call_args.args[2:] == (125, 98)


@patch(
    "app.routes.save_bird_track_points",
    return_value=(1, 0),
)
@patch(
    "app.routes.get_analytics_device_context",
    return_value={"node_id": "CAM-01"},
)
@patch("app.routes.settings.ai_ingest_token", "secret-token")
def test_ai_detection_endpoint_stores_tracked_positions(
    mock_context,
    mock_save,
):
    with TestClient(app) as client:
        response = client.post(
            "/api/ai/detections",
            headers={"X-AI-Ingest-Token": "secret-token"},
            json={
                "cameraId": "CAM-01",
                "timestamp": int(datetime.now(timezone.utc).timestamp()),
                "detections": [
                    {
                        "class": "swiftlet",
                        "confidence": 0.94,
                        "trackId": 21,
                        "bbox": [120, 80, 165, 140],
                    },
                ],
            },
        )

    assert response.status_code == 202
    assert response.json() == {"accepted": 1, "duplicate": 0, "ignored": 0}
    mock_context.assert_called_once_with("CAM-01")
    assert mock_save.call_args.kwargs["camera_id"] == "CAM-01"
    assert mock_save.call_args.kwargs["detections"][0]["track_id"] == 21


def test_bird_movement_storage_is_idempotent_and_ignores_untracked_objects():
    cursor = MagicMock()
    outcomes = iter((1, 0))

    def execute(*_args):
        cursor.rowcount = next(outcomes)

    cursor.execute.side_effect = execute
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection
    detection = {
        "object_class": "swiftlet",
        "confidence": 0.94,
        "track_id": 21,
        "bbox": (120, 80, 165, 140),
    }

    with patch(
        "app.repository.get_connection",
        return_value=connection_context,
    ):
        result = save_bird_track_points(
            camera_id="CAM-01",
            observed_at=datetime.now(timezone.utc),
            detections=[
                detection,
                detection,
                {
                    "object_class": "snake",
                    "confidence": 0.9,
                    "track_id": 22,
                    "bbox": (10, 10, 20, 20),
                },
                {
                    "object_class": "swiftlet",
                    "confidence": 0.9,
                    "track_id": None,
                    "bbox": (20, 20, 30, 30),
                },
            ],
            context={
                "farm_id": "00000000-0000-4000-8000-000000000001",
                "farm_name": "Farm One",
                "zone_id": None,
            },
        )

    assert result == (1, 1)
    assert cursor.execute.call_count == 2
    insert_parameters = cursor.execute.call_args_list[0].args[1]
    assert insert_parameters[6:8] == (142.5, 110.0)


@patch(
    "app.services.get_bird_analytics",
    return_value=[
        (
            datetime(2026, 11, 18, tzinfo=timezone.utc),
            12,
            8,
            1,
        ),
    ],
)
def test_bird_analytics_uses_daily_buckets_and_camera_scope(mock_query):
    now = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)

    result = get_bird_analytics_data(
        ["CAM-01", "CAM-02"],
        "7d",
        now=now,
        camera_id="CAM-01",
    )

    assert result["camera_id"] == "CAM-01"
    assert result["entries"] == 12
    assert result["exits"] == 8
    assert result["net_change"] == 4
    mock_query.assert_called_once_with(
        ["CAM-01", "CAM-02"],
        now - timedelta(days=7),
        now,
        "day",
        "CAM-01",
    )


@patch(
    "app.routes.get_bird_analytics_data",
    return_value={
        "period": "7d",
        "start": "2026-11-12T00:00:00+00:00",
        "end": "2026-11-19T00:00:00+00:00",
        "camera_id": "CAM-01",
        "camera_count": 1,
        "entries": 5,
        "exits": 3,
        "net_change": 2,
        "series": [],
    },
)
@patch(
    "app.routes.get_monitorable_devices",
    return_value=[{"node_id": "CAM-01"}],
)
def test_bird_analytics_scopes_daily_query_to_authorized_camera(
    _mock_devices,
    mock_analytics,
):
    with TestClient(app) as client:
        response = client.get(
            "/api/analytics/birds",
            params={"period": "7d", "camera_id": "CAM-01"},
            headers={"Authorization": "Bearer user-token"},
        )

    assert response.status_code == 200
    assert response.json()["camera_id"] == "CAM-01"
    mock_analytics.assert_called_once_with(
        ["CAM-01"],
        "7d",
        camera_id="CAM-01",
    )


@patch("app.routes.get_bird_analytics_data")
@patch(
    "app.routes.get_monitorable_devices",
    return_value=[{"node_id": "CAM-01"}],
)
def test_bird_analytics_rejects_camera_outside_authorized_scope(
    _mock_devices,
    mock_analytics,
):
    with TestClient(app) as client:
        response = client.get(
            "/api/analytics/birds",
            params={"camera_id": "CAM-02"},
            headers={"Authorization": "Bearer user-token"},
        )

    assert response.status_code == 403
    mock_analytics.assert_not_called()


@patch(
    "app.routes.get_bird_movement_history_data",
    return_value={
        "camera_id": "CAM-01",
        "period": "24h",
        "start": "2026-11-18T00:00:00+00:00",
        "end": "2026-11-19T00:00:00+00:00",
        "points": [],
    },
)
@patch(
    "app.routes.get_monitorable_devices",
    return_value=[{"node_id": "CAM-01"}],
)
def test_bird_movement_history_requires_authorized_camera(
    _mock_devices,
    mock_history,
):
    with TestClient(app) as client:
        response = client.get(
            "/api/analytics/bird-movements",
            params={"camera_id": "CAM-01", "period": "24h"},
            headers={"Authorization": "Bearer user-token"},
        )

    assert response.status_code == 200
    assert response.json()["camera_id"] == "CAM-01"
    mock_history.assert_called_once_with(
        "CAM-01",
        "24h",
        track_id=None,
        limit=500,
    )


@patch("app.routes.get_bird_movement_history_data")
@patch(
    "app.routes.get_monitorable_devices",
    return_value=[{"node_id": "CAM-01"}],
)
def test_bird_movement_history_rejects_camera_outside_authorized_scope(
    _mock_devices,
    mock_history,
):
    with TestClient(app) as client:
        response = client.get(
            "/api/analytics/bird-movements",
            params={"camera_id": "CAM-02"},
            headers={"Authorization": "Bearer user-token"},
        )

    assert response.status_code == 403
    mock_history.assert_not_called()


@patch("app.routes.get_ai_events_data", return_value=[])
@patch(
    "app.routes.get_monitorable_devices",
    return_value=[{"node_id": "CAM-01"}, {"node_id": "CAM-02"}],
)
def test_ai_event_list_accepts_type_time_camera_and_pagination_filters(
    mock_devices,
    mock_events,
):
    with TestClient(app) as client:
        response = client.get(
            "/api/analytics/ai-events",
            params={
                "source_type": "vision",
                "event_type": "PREDATOR_DETECTED",
                "camera_id": "CAM-02",
                "start": "2026-11-18T00:00:00+00:00",
                "end": "2026-11-19T00:00:00+00:00",
                "limit": 25,
                "offset": 50,
            },
            headers={"Authorization": "Bearer user-token"},
        )

    assert response.status_code == 200
    mock_devices.assert_called_once_with(
        "Bearer user-token",
        farm_id=None,
        zone_id=None,
    )
    args, kwargs = mock_events.call_args
    assert args[:3] == (["CAM-01", "CAM-02"], "7d", "vision")
    assert kwargs["event_type"] == "PREDATOR_DETECTED"
    assert kwargs["camera_id"] == "CAM-02"
    assert kwargs["start"] == datetime(2026, 11, 18, tzinfo=timezone.utc)
    assert kwargs["end"] == datetime(2026, 11, 19, tzinfo=timezone.utc)
    assert kwargs["limit"] == 25
    assert kwargs["offset"] == 50


@patch("app.routes.get_ai_events_data")
@patch("app.routes.get_monitorable_devices")
def test_ai_event_list_rejects_partial_or_timezone_free_custom_range(
    mock_devices,
    mock_events,
):
    with TestClient(app) as client:
        partial_response = client.get(
            "/api/analytics/ai-events",
            params={"start": "2026-11-18T00:00:00Z"},
            headers={"Authorization": "Bearer user-token"},
        )
        naive_response = client.get(
            "/api/analytics/ai-events",
            params={
                "start": "2026-11-18T00:00:00",
                "end": "2026-11-19T00:00:00",
            },
            headers={"Authorization": "Bearer user-token"},
        )

    assert partial_response.status_code == 422
    assert naive_response.status_code == 422
    mock_devices.assert_not_called()
    mock_events.assert_not_called()


@patch("app.routes.get_ai_events_data")
@patch(
    "app.routes.get_monitorable_devices",
    return_value=[{"node_id": "CAM-01"}],
)
def test_ai_event_list_rejects_camera_outside_authorized_scope(
    mock_devices,
    mock_events,
):
    with TestClient(app) as client:
        response = client.get(
            "/api/analytics/ai-events",
            params={"camera_id": "CAM-02"},
            headers={"Authorization": "Bearer user-token"},
        )

    assert response.status_code == 403
    mock_devices.assert_called_once()
    mock_events.assert_not_called()


@patch(
    "app.routes.get_ai_event_detail_data",
    return_value={
        "id": "00000000-0000-4000-8000-000000000010",
        "source_type": "vision",
        "camera_id": "CAM-01",
        "event_type": "PREDATOR_DETECTED",
        "label": "snake",
        "confidence": 0.9,
        "observed_at": "2026-11-19T00:00:00+00:00",
        "farm_id": "00000000-0000-4000-8000-000000000001",
        "farm_code": "FARM-01",
        "farm_name": "Farm One",
        "zone_id": None,
        "zone_code": None,
        "zone_name": None,
        "payload": {"bbox": [1, 2, 20, 30]},
    },
)
@patch(
    "app.routes.get_monitorable_devices",
    return_value=[{"node_id": "CAM-01"}],
)
def test_ai_event_detail_returns_authorized_event_with_payload(
    mock_devices,
    mock_detail,
):
    event_id = "00000000-0000-4000-8000-000000000010"
    with TestClient(app) as client:
        response = client.get(
            f"/api/analytics/ai-events/{event_id}",
            headers={"Authorization": "Bearer user-token"},
        )

    assert response.status_code == 200
    assert response.json()["payload"]["bbox"] == [1, 2, 20, 30]
    mock_devices.assert_called_once()
    mock_detail.assert_called_once_with(
        ["CAM-01"],
        UUID(event_id),
    )


@patch(
    "app.routes.get_ai_event_detail_data",
    return_value=None,
)
@patch(
    "app.routes.get_monitorable_devices",
    return_value=[{"node_id": "CAM-01"}],
)
def test_ai_event_detail_does_not_expose_events_outside_accessible_devices(
    _mock_devices,
    mock_detail,
):
    with TestClient(app) as client:
        response = client.get(
            "/api/analytics/ai-events/"
            "00000000-0000-4000-8000-000000000011",
            headers={"Authorization": "Bearer user-token"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "AI event not found"
    mock_detail.assert_called_once()


@patch(
    "app.routes.get_analytics_device_context",
    return_value={
        "node_id": "CAM-01",
        "device_id": "device-01",
        "farm_id": "00000000-0000-4000-8000-000000000001",
        "farm_code": "FARM-01",
        "farm_name": "Farm One",
        "zone_id": "00000000-0000-4000-8000-000000000002",
        "zone_code": "ZONE-01",
        "zone_name": "Zone One",
        "recipient_user_ids": ["00000000-0000-4000-8000-000000000003"],
    },
)
@patch(
    "app.routes.store_ai_event",
    return_value=UUID(
        "00000000-0000-4000-8000-000000000004",
    ),
)
@patch("app.routes.settings.ai_ingest_token", "secret-token")
def test_vision_event_is_validated_mapped_and_accepted(
    mock_store,
    mock_context,
):
    with TestClient(app) as client:
        response = client.post(
            "/api/ai/events",
            headers={"X-AI-Ingest-Token": "secret-token"},
            json={
                "eventId": "00000000-0000-4000-8000-000000000005",
                "cameraId": "CAM-01",
                "eventType": "PREDATOR_DETECTED",
                "class": "snake",
                "confidence": 0.91,
                "timestamp": int(datetime.now(timezone.utc).timestamp()),
                "bbox": [10, 20, 40, 60],
                "snapshot": "https://storage.example/snapshot.jpg",
            },
        )

    assert response.status_code == 202
    assert response.json() == {
        "event_id": "00000000-0000-4000-8000-000000000004",
        "accepted": True,
        "duplicate": False,
    }
    mock_context.assert_called_once_with("CAM-01")
    assert mock_store.call_args.args[0] == "vision"
    assert mock_store.call_args.args[2]["farm_code"] == "FARM-01"
    assert mock_store.call_args.args[2]["zone_code"] == "ZONE-01"


@patch("app.routes.store_ai_event", return_value=None)
@patch(
    "app.routes.get_analytics_device_context",
    return_value={"node_id": "CAM-01"},
)
@patch("app.routes.settings.ai_ingest_token", "secret-token")
def test_audio_event_duplicate_returns_explicit_duplicate_result(
    mock_context,
    _mock_store,
):
    with TestClient(app) as client:
        response = client.post(
            "/api/ai/audio/events",
            headers={"X-AI-Ingest-Token": "secret-token"},
            json={
                "cameraId": "CAM-01",
                "eventType": "AUDIO_ANOMALY",
                "label": "predator_sound",
                "confidence": 0.88,
                "timestamp": int(datetime.now(timezone.utc).timestamp()),
                "audioRms": 0.72,
                "threshold": 0.5,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "event_id": None,
        "accepted": False,
        "duplicate": True,
    }
    mock_context.assert_called_once_with("CAM-01")


@patch("app.routes.get_analytics_device_context")
@patch("app.routes.settings.ai_ingest_token", "secret-token")
def test_invalid_vision_event_is_rejected_before_mapping(mock_context):
    with TestClient(app) as client:
        response = client.post(
            "/api/ai/events",
            headers={"X-AI-Ingest-Token": "secret-token"},
            json={
                "cameraId": "CAM-01",
                "eventType": "PREDATOR_DETECTED",
                "class": "snake",
                "confidence": 1.4,
                "timestamp": int(datetime.now(timezone.utc).timestamp()),
                "bbox": [10, 20, 5, 60],
            },
        )

    assert response.status_code == 422
    mock_context.assert_not_called()


def test_vision_event_schema_rejects_invalid_box_and_audio_schema_rejects_extra():
    with pytest.raises(ValueError, match="bbox"):
        AIVisionEventRequest.model_validate(
            {
                "cameraId": "CAM-01",
                "eventType": "PREDATOR_DETECTED",
                "class": "snake",
                "confidence": 0.9,
                "timestamp": 1728135000,
                "bbox": [20, 20, 10, 40],
            },
        )

    with pytest.raises(ValueError):
        AIAudioEventRequest.model_validate(
            {
                "cameraId": "CAM-01",
                "eventType": "AUDIO_ANOMALY",
                "label": "noise",
                "confidence": 0.9,
                "timestamp": 1728135000,
                "unknown": True,
            },
        )

    with pytest.raises(ValueError):
        AIVisionEventRequest.model_validate(
            {
                "cameraId": "CAM-01",
                "eventType": "PREDATOR_DETECTED",
                "class": "snake",
                "confidence": float("nan"),
                "timestamp": 1728135000,
            },
        )

    with pytest.raises(ValueError, match="bbox"):
        AIVisionEventRequest.model_validate(
            {
                "cameraId": "CAM-01",
                "eventType": "PREDATOR_DETECTED",
                "class": "snake",
                "confidence": 0.9,
                "timestamp": 1728135000,
                "bbox": [-1, 0, 10, 10],
            },
        )


@patch("app.routes.settings.ai_ingest_token", "secret-token")
def test_ai_counts_endpoint_rejects_invalid_ingest_token():
    with TestClient(app) as client:
        response = client.post(
            "/api/ai/counts",
            headers={"X-AI-Ingest-Token": "wrong-token"},
            json={
                "cameraId": "CAM-01",
                "timestamp": 1728135000,
                "entryCount": 125,
                "exitCount": 98,
                "netChange": 27,
            },
        )

    assert response.status_code == 401


@patch("app.routes.get_authorized_farms", return_value=[{"farm_id": "farm-1"}])
def test_harvest_scope_rejects_zone_without_authorized_farm(mock_farms):
    with pytest.raises(HTTPException) as exc_info:
        _authorized_farm_ids("Bearer token", "farm-2", None)

    assert getattr(exc_info.value, "status_code", None) == 403
    mock_farms.assert_called_once_with("Bearer token")


@patch("app.routes.get_authorized_zones", return_value=[{"zone_id": "zone-1"}])
@patch("app.routes.get_authorized_farms", return_value=[{"farm_id": "farm-1"}])
def test_harvest_scope_accepts_only_authorized_farm_and_zone(
    _mock_farms,
    _mock_zones,
):
    assert _authorized_farm_ids(
        "Bearer token",
        "farm-1",
        "zone-1",
    ) == ["farm-1"]


def test_telemetry_reports_generate_csv_and_pdf():
    analytics = _telemetry_result()

    csv_report = telemetry_csv(analytics)
    pdf_report = telemetry_pdf(analytics)

    assert csv_report.startswith(b"\xef\xbb\xbf")
    assert b"Temperature" in csv_report
    assert pdf_report.startswith(b"%PDF")
