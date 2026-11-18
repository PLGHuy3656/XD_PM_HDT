from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.reports import telemetry_csv, telemetry_pdf
from app.routes import _authorized_farm_ids
from app.schemas import AICountSnapshotRequest


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
@patch("app.routes.settings.ai_ingest_token", "secret-token")
def test_ai_counts_endpoint_authenticates_and_stores_contract_payload(
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
