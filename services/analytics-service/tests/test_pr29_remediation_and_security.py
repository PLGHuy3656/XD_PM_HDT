from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.alerting import _record_alert
from app.config import Settings
from app.main import app
from app.reports import _csv_safe_cell, telemetry_csv, telemetry_pdf
from app.schemas import HarvestRecordRequest


class TestCanonicalEventAndAlerting:
    @patch("app.alerting.open_analytics_alert")
    def test_record_alert_emits_canonical_v1_envelope(self, mock_open):
        _record_alert(
            context={
                "farm_id": "11111111-1111-1111-1111-111111111111",
                "farm_code": "FARM-01",
                "farm_name": "Nha Yen 01",
                "zone_name": "Tang 1",
                "recipient_user_ids": ["22222222-2222-2222-2222-222222222222"],
            },
            node_id="ESP32-01",
            alert_key="ESP32-01:threshold_exceeded:temperature",
            alert_type="threshold_exceeded",
            metric="temperature",
            value=36.5,
            threshold=32.0,
            direction="above",
            baseline={},
        )

        mock_open.assert_called_once()
        event = mock_open.call_args.kwargs["event"]
        assert event["eventVersion"] == "1.0"
        assert event["eventType"] == "environment.threshold_exceeded"
        assert event["producer"] == "analytics-service"
        assert event["eventId"] == event["correlationId"]
        assert "occurredAt" in event
        assert event["payload"]["recipientUserIds"] == [
            "22222222-2222-2222-2222-222222222222"
        ]
        assert event["payload"]["nodeId"] == "ESP32-01"
        assert event["payload"]["value"] == 36.5


class TestReportSafety:
    def test_csv_neutralizes_formula_injection_and_preserves_numbers(self):
        assert _csv_safe_cell("=CMD|' /C calc'!A0") == "'=CMD|' /C calc'!A0"
        assert _csv_safe_cell("+1+1") == "'+1+1"
        assert _csv_safe_cell("-2+3") == "'-2+3"
        assert _csv_safe_cell("@SUM(A1:A2)") == "'@SUM(A1:A2)"
        assert _csv_safe_cell("\t=1+1") == "'\t=1+1"
        # Legitimate numbers and None must not be mutated
        assert _csv_safe_cell(-1.5) == -1.5
        assert _csv_safe_cell(0.0) == 0.0
        assert _csv_safe_cell(None) is None

    def test_csv_and_pdf_handle_empty_and_special_chars_safely(self):
        empty_stats = {"average": None, "minimum": None, "maximum": None}
        analytics = {
            "period": "24h",
            "start": "2026-11-18T00:00:00+00:00",
            "end": "2026-11-19T00:00:00+00:00",
            "device_count": 1,
            "sample_count": 0,
            "summary": {
                m: empty_stats
                for m in ("temperature", "humidity", "co2", "lux", "audio_rms")
            },
            "series": [
                {
                    "timestamp": "=HYPERLINK(\"http://evil\")",
                    "samples": 0,
                    **{
                        m: empty_stats
                        for m in ("temperature", "humidity", "co2", "lux", "audio_rms")
                    },
                }
            ],
        }
        csv_bytes = telemetry_csv(analytics)
        assert b"'=HYPERLINK" in csv_bytes
        pdf_bytes = telemetry_pdf(analytics)
        assert pdf_bytes.startswith(b"%PDF")


class TestSecurityAndFailClosed:
    @patch("app.authorization.httpx.get", side_effect=httpx.ConnectError("down"))
    def test_management_unavailable_fails_closed_503(self, _mock_get):
        with TestClient(app) as client:
            res = client.get(
                "/api/analytics/telemetry?period=24h",
                headers={"Authorization": "Bearer any-token"},
            )
        assert res.status_code == 503

    @patch(
        "app.authorization.httpx.get",
        return_value=httpx.Response(401, json={"detail": "unauthorized"}),
    )
    def test_invalid_bearer_token_returns_401(self, _mock_get):
        with TestClient(app) as client:
            res = client.get(
                "/api/analytics/telemetry?period=24h",
                headers={"Authorization": "Bearer expired"},
            )
        assert res.status_code == 401

    @patch("app.routes.settings.ai_ingest_token", "")
    def test_ai_ingest_unconfigured_fails_closed_503(self):
        with TestClient(app) as client:
            res = client.post(
                "/api/ai/counts",
                headers={"X-AI-Ingest-Token": "anything"},
                json={
                    "cameraId": "CAM-01",
                    "timestamp": int(datetime.now(timezone.utc).timestamp()),
                    "entryCount": 10,
                    "exitCount": 5,
                    "netChange": 5,
                },
            )
        assert res.status_code == 503

    @patch("app.routes.settings.ai_ingest_token", "valid-token")
    def test_ai_ingest_rejects_future_timestamp_422(self):
        future_ts = int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp())
        with TestClient(app) as client:
            res = client.post(
                "/api/ai/counts",
                headers={"X-AI-Ingest-Token": "valid-token"},
                json={
                    "cameraId": "CAM-01",
                    "timestamp": future_ts,
                    "entryCount": 10,
                    "exitCount": 5,
                    "netChange": 5,
                },
            )
        assert res.status_code == 422

    def test_harvest_rejects_negative_values(self):
        with pytest.raises(ValueError):
            HarvestRecordRequest.model_validate(
                {
                    "farm_id": "11111111-1111-1111-1111-111111111111",
                    "harvest_date": "2026-11-19",
                    "nest_count": -1,
                    "yield_kg": "1.500",
                }
            )
        with pytest.raises(ValueError):
            HarvestRecordRequest.model_validate(
                {
                    "farm_id": "11111111-1111-1111-1111-111111111111",
                    "harvest_date": "2026-11-19",
                    "nest_count": 5,
                    "yield_kg": "-0.100",
                }
            )

    def test_zone_without_farm_id_returns_422(self):
        with TestClient(app) as client:
            res = client.get(
                "/api/analytics/harvest?zone_id=22222222-2222-2222-2222-222222222222",
                headers={"Authorization": "Bearer tok"},
            )
        assert res.status_code == 422


class TestConfigMigrationsAndUnifiedApp:
    def test_config_defaults_and_compose_env_assembly(self):
        fresh = Settings(_env_file=None)
        assert fresh.database_url == ""
        assert fresh.analytics_service_token == ""
        assert fresh.ai_ingest_token == ""
        assert fresh.rabbitmq_url == ""
        assert fresh.event_exchange == "swiftlet.domain.events"
        assert fresh.service_port == 8005
        assert fresh.telemetry_source == "analytics_db"

        composed = Settings(
            _env_file=None,
            ANALYTICS_DATABASE_URL="postgresql://u:p@pg:5432/analytics_db",
            RABBITMQ_HOST="rabbitmq",
            RABBITMQ_PORT=5672,
            RABBITMQ_USER="swiftlet",
            RABBITMQ_PASSWORD="p@ss/word",
            RABBITMQ_ENABLED="true",
        )
        assert composed.database_url == "postgresql://u:p@pg:5432/analytics_db"
        assert composed.rabbitmq_url == "amqp://swiftlet:p%40ss%2Fword@rabbitmq:5672/"

    def test_migrations_are_isolated_and_clean(self):
        mig_dir = Path(__file__).resolve().parents[1] / "database" / "migrations"
        assert (mig_dir / "001_initial_analytics_schema.sql").exists()
        assert (mig_dir / "002_analytics_domains.sql").exists()
        assert not (mig_dir / "001_telemetry_analytics_index.sql").exists()

        sql_002 = (mig_dir / "002_analytics_domains.sql").read_text(encoding="utf-8")
        assert "CONCURRENTLY" not in sql_002
        assert "REFERENCES users(" not in sql_002
        assert "public.analytics_telemetry_samples" in sql_002
        assert "schema_migrations" in sql_002

    def test_unified_app_exposes_both_olap_and_operational_routes(self):
        paths = set(app.openapi()["paths"].keys())
        # CP9 OLAP routes (origin/main)
        assert "/health" in paths
        assert "/api/v1/analytics/farms/{farm_id}/summary" in paths
        assert "/api/v1/analytics/farms/{farm_id}/trends" in paths
        assert "/api/v1/analytics/trends" in paths
        # PR #29 Operational routes (HaoHoc)
        assert "/api/analytics/telemetry" in paths
        assert "/api/analytics/telemetry/report.csv" in paths
        assert "/api/analytics/telemetry/report.pdf" in paths
        assert "/api/analytics/birds" in paths
        assert "/api/analytics/alerts" in paths
        assert "/api/analytics/harvest" in paths
        assert "/api/ai/counts" in paths
