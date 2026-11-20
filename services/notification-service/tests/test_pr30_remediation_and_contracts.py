"""PR #30 Gate 1 remediation: Canonical V1 event contracts, security, RBAC, poison-message, and schema isolation tests."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.consumer import (
    SUPPORTED_EVENT_TYPES,
    _sanitize_payload_data,
    adapt_incoming_event,
    process_event,
)
from app.main import app
from app.repositories import notification_content


class TestCanonicalEventContracts:
    @pytest.mark.asyncio
    async def test_ai_predator_detected_canonical_event_adapts_and_resolves_recipients(self):
        uid = str(uuid.uuid4())
        eid = str(uuid.uuid4())
        canonical = {
            "eventId": eid,
            "eventType": "ai.predator.detected",
            "eventVersion": "1.0",
            "occurredAt": "2026-11-19T12:00:00Z",
            "producer": "ai-service",
            "correlationId": None,
            "payload": {
                "farmId": "FARM-01",
                "zoneId": "ZONE-A",
                "cameraId": "CAM-01",
                "predatorClass": "snake",
                "confidence": 0.94,
                "snapshotRef": "CAM-01_snake.jpg",
            },
        }
        with patch("app.consumer.resolve_farm_recipients", new=AsyncMock(return_value=[uid])):
            adapted = await adapt_incoming_event(canonical)

        assert adapted is not None
        assert adapted["event_id"] == eid
        assert adapted["event_type"] == "ai.predator.detected"
        assert adapted["recipient_user_ids"] == [uid]
        title, msg, cat = notification_content(adapted["event_type"], adapted["data"], uid)
        assert cat == "danger"
        assert "snake" in msg and "CAM-01" in msg

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "event_type,extra_payload,expected_cat",
        [
            ("iot.command.failed", {"deviceId": "SWC-NODE-001", "action": "SET_RELAY", "reason": "Timeout"}, "danger"),
            ("iot.device.offline", {"deviceId": "SWC-NODE-001", "status": "OFFLINE"}, "danger"),
            ("iot.device.online", {"deviceId": "SWC-NODE-001", "status": "ONLINE"}, "info"),
            ("iot.environment.high_temperature.started", {"deviceId": "SWC-NODE-001", "metric": "temperature", "value": 33.2, "unit": "C"}, "danger"),
            ("iot.environment.high_temperature.recovered", {"deviceId": "SWC-NODE-001", "metric": "temperature", "value": 29.8, "unit": "C"}, "info"),
            ("iot.audio.fault.started", {"deviceId": "SWC-NODE-001", "metric": "audio", "value": "FAULT"}, "danger"),
        ],
    )
    async def test_iot_canonical_events_adapt_and_format(self, event_type, extra_payload, expected_cat):
        uid = str(uuid.uuid4())
        canonical = {
            "eventId": str(uuid.uuid4()),
            "eventType": event_type,
            "eventVersion": "1.0",
            "occurredAt": "2026-11-19T12:00:00Z",
            "producer": "iot-service",
            "correlationId": str(uuid.uuid4()),
            "payload": {"farmId": "FARM-01", "zoneId": "ZONE-01", **extra_payload},
        }
        with patch("app.consumer.resolve_farm_recipients", new=AsyncMock(return_value=[uid])):
            adapted = await adapt_incoming_event(canonical)

        assert adapted is not None
        assert adapted["event_type"] == event_type
        _, _, cat = notification_content(event_type, adapted["data"], uid)
        assert cat == expected_cat

    @pytest.mark.asyncio
    async def test_unsupported_event_version_raises_value_error(self):
        bad_ver = {
            "eventId": str(uuid.uuid4()),
            "eventType": "iot.device.offline",
            "eventVersion": "2.0",
            "occurredAt": "2026-11-19T12:00:00Z",
            "producer": "iot-service",
            "payload": {"farmId": "FARM-01"},
        }
        with pytest.raises(ValueError, match="Unsupported canonical eventVersion"):
            await adapt_incoming_event(bad_ver)

    @pytest.mark.asyncio
    async def test_unknown_event_type_and_missing_recipients_are_dropped_cleanly(self):
        unknown = {
            "eventId": str(uuid.uuid4()),
            "eventType": "unknown.service.event",
            "eventVersion": "1.0",
            "payload": {"farmId": "FARM-01"},
        }
        assert await adapt_incoming_event(unknown) is None

        no_rec = {
            "eventId": str(uuid.uuid4()),
            "eventType": "iot.device.offline",
            "eventVersion": "1.0",
            "payload": {"farmId": "FARM-NO-USERS", "deviceId": "SWC-1"},
        }
        with patch("app.consumer.resolve_farm_recipients", new=AsyncMock(return_value=[])):
            assert await adapt_incoming_event(no_rec) is None


class TestSecurityRbacAndSanitization:
    def test_missing_bearer_token_returns_401(self):
        client = TestClient(app)
        assert client.get("/api/notifications").status_code == 401
        assert client.post(f"/api/notifications/{uuid.uuid4()}/read").status_code == 401
        assert client.post("/api/notifications/read-all").status_code == 401

    def test_idor_cross_user_mark_read_returns_404(self):
        client = TestClient(app)
        user_a = {"id": str(uuid.uuid4()), "email": "owner.a@local"}
        with (
            patch("app.routes.get_user_from_authorization", new=AsyncMock(return_value=user_a)),
            patch("app.repositories.mark_notification_read", return_value=False) as mock_mark,
        ):
            nid = str(uuid.uuid4())
            res = client.post(
                f"/api/notifications/{nid}/read",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert res.status_code == 404
            mock_mark.assert_called_once_with(nid, user_a["id"])

    def test_untrusted_web_push_endpoint_rejected_422(self):
        client = TestClient(app)
        res = client.post(
            "/api/notifications/subscriptions",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "endpoint": "https://evil.attacker.example/push",
                "keys": {"p256dh": "abc", "auth": "def"},
            },
        )
        assert res.status_code == 422

    def test_payload_sanitization_strips_secrets_and_local_paths(self):
        raw = {
            "deviceId": "SWC-1",
            "password": "leaked-password",
            "access_token": "jwt-secret",
            "snapshot": r"C:\Users\admin\secret\rat.jpg",
            "linux_path": "/tmp/private/snake.jpg",
        }
        clean = _sanitize_payload_data(raw)
        assert "password" not in clean
        assert "access_token" not in clean
        assert clean["snapshot"] == "rat.jpg"
        assert clean["linux_path"] == "snake.jpg"

    def test_config_defaults_have_no_hardcoded_secrets_and_canonical_exchange(self):
        fresh = Settings(_env_file=None)
        assert fresh.database_url == ""
        assert fresh.rabbitmq_url == ""
        assert fresh.smtp_password == ""
        assert fresh.internal_service_token == ""
        assert fresh.event_exchange == "swiftlet.domain.events"
        assert fresh.service_port == 8004

    def test_config_assembles_rabbitmq_url_from_compose_env_vars(self):
        cfg = Settings(
            _env_file=None,
            RABBITMQ_HOST="rabbitmq",
            RABBITMQ_PORT=5672,
            RABBITMQ_USER="swiftlet",
            RABBITMQ_PASSWORD="p@ss/word",
            RABBITMQ_ENABLED="true",
        )
        assert cfg.rabbitmq_url == "amqp://swiftlet:p%40ss%2Fword@rabbitmq:5672/"

        disabled = Settings(
            _env_file=None,
            RABBITMQ_HOST="rabbitmq",
            RABBITMQ_USER="swiftlet",
            RABBITMQ_PASSWORD="secret",
            RABBITMQ_ENABLED="false",
        )
        assert disabled.rabbitmq_url == ""

    def test_schema_sql_has_no_cross_service_users_fk(self):
        schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
        sql = schema_path.read_text(encoding="utf-8")
        assert "REFERENCES users(" not in sql
        assert "UNIQUE (event_id, user_id)" in sql
        assert "schema_migrations" in sql


class TestInt03ManagementRecipientContract:
    """INT03: the real Management contract (path, header, response shape) — not mocked away."""

    @pytest.mark.asyncio
    async def test_resolve_farm_recipients_uses_management_internal_contract(self):
        import httpx as _httpx
        from app import consumer
        owner = "00000000-0000-0000-0000-00000000000a"
        tech = "00000000-0000-0000-0000-00000000000c"
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["headers"] = dict(request.headers)
            return _httpx.Response(200, json={"farm_id": "F", "farm_code": "C", "owner_id": owner, "technician_ids": [tech, "not-a-uuid"]})

        real_client = _httpx.AsyncClient

        def fake_client(*args, **kwargs):
            kwargs["transport"] = _httpx.MockTransport(handler)
            return real_client(*args, **kwargs)

        with patch.object(consumer.settings, "management_service_url", "http://mgmt:8001"), \
             patch.object(consumer.settings, "internal_service_token", "k" * 40), \
             patch.object(consumer.httpx, "AsyncClient", side_effect=fake_client):
            ids = await consumer.resolve_farm_recipients("F")
        assert ids == [owner, tech]
        assert seen["url"].endswith("/internal/v1/farms/F/recipients")
        assert seen["headers"].get("x-internal-service-key") == "k" * 40
        assert "x-internal-service-token" not in seen["headers"]

    @pytest.mark.asyncio
    async def test_resolve_farm_recipients_fail_closed_on_error(self):
        import httpx as _httpx
        from app import consumer
        real_client = _httpx.AsyncClient

        def fake_client(*args, **kwargs):
            kwargs["transport"] = _httpx.MockTransport(lambda r: _httpx.Response(401, json={}))
            return real_client(*args, **kwargs)

        with patch.object(consumer.settings, "management_service_url", "http://mgmt:8001"), \
             patch.object(consumer.httpx, "AsyncClient", side_effect=fake_client):
            assert await consumer.resolve_farm_recipients("F") == []
