from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.routes import get_telemetry_analytics
from app.services import get_telemetry_analytics_data


def _row(bucket, count, value):
    return (
        bucket,
        count,
        value,
        value - 1 if value is not None else None,
        value + 1 if value is not None else None,
        *(
            item
            for _ in range(4)
            for item in (
                value,
                value - 1 if value is not None else None,
                value + 1 if value is not None else None,
            )
        ),
    )


@patch("app.services.get_telemetry_analytics")
def test_telemetry_analytics_returns_summary_and_bucket_series(mock_query):
    end = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
    sample_bucket = datetime(2026, 11, 18, 11, tzinfo=timezone.utc)
    mock_query.return_value = [
        _row(None, 4, 25.0),
        _row(sample_bucket, 4, 25.0),
    ]

    result = get_telemetry_analytics_data(["node-01"], "24h", now=end)

    assert result["start"] == "2026-11-17T12:00:00+00:00"
    assert result["end"] == "2026-11-18T12:00:00+00:00"
    assert result["device_count"] == 1
    assert result["sample_count"] == 4
    assert result["summary"]["temperature"] == {
        "average": 25.0,
        "minimum": 24.0,
        "maximum": 26.0,
    }
    assert result["series"][0]["timestamp"] == sample_bucket.isoformat()
    assert mock_query.call_args.args == (
        ["node-01"],
        datetime(2026, 11, 17, 12, tzinfo=timezone.utc),
        end,
        "hour",
    )


@patch("app.services.get_telemetry_analytics")
def test_telemetry_analytics_returns_empty_statistics_without_devices(
    mock_query,
):
    result = get_telemetry_analytics_data([], "1h")

    assert result["device_count"] == 0
    assert result["sample_count"] == 0
    assert result["series"] == []
    assert result["summary"]["temperature"] == {
        "average": None,
        "minimum": None,
        "maximum": None,
    }
    mock_query.assert_not_called()


@patch("app.routes.get_telemetry_analytics_data")
@patch("app.routes.get_monitorable_devices")
def test_endpoint_uses_only_authorized_farm_and_zone_devices(
    mock_get_devices,
    mock_get_analytics,
):
    mock_get_devices.return_value = [{"node_id": "node-01"}]
    mock_get_analytics.return_value = {"period": "7d"}

    result = get_telemetry_analytics(
        period="7d",
        farm_id="farm-01",
        zone_id="zone-02",
        authorization="Bearer token",
    )

    mock_get_devices.assert_called_once_with(
        "Bearer token",
        farm_id="farm-01",
        zone_id="zone-02",
    )
    mock_get_analytics.assert_called_once_with(["node-01"], "7d")
    assert result == {"period": "7d"}


@patch("app.routes.get_telemetry_analytics_data")
@patch("app.routes.get_monitorable_devices")
def test_telemetry_endpoint_returns_validated_analytics_response(
    mock_get_devices,
    mock_get_analytics,
):
    mock_get_devices.return_value = [{"node_id": "node-01"}]
    mock_get_analytics.return_value = {
        "period": "1h",
        "start": "2026-11-18T11:00:00+00:00",
        "end": "2026-11-18T12:00:00+00:00",
        "bucket": "minute",
        "device_count": 1,
        "sample_count": 0,
        "summary": {
            metric: {
                "average": None,
                "minimum": None,
                "maximum": None,
            }
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

    with TestClient(app) as client:
        response = client.get(
            "/api/analytics/telemetry?period=1h",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    assert response.json()["bucket"] == "minute"
    assert response.json()["sample_count"] == 0


@patch("app.authorization.httpx.get")
def test_management_access_request_includes_bearer_and_filters(mock_get):
    from app.authorization import get_monitorable_devices
    import httpx

    mock_get.return_value = httpx.Response(
        200,
        json=[{"node_id": "node-01"}],
    )

    devices = get_monitorable_devices(
        "Bearer token",
        farm_id="farm-01",
        zone_id="zone-02",
    )

    assert devices == [{"node_id": "node-01"}]
    assert mock_get.call_args.kwargs["headers"] == {
        "Authorization": "Bearer token",
    }
    assert mock_get.call_args.kwargs["params"] == {
        "farm_id": "farm-01",
        "zone_id": "zone-02",
    }
