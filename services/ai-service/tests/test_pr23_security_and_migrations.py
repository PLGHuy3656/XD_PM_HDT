"""PR #23 security, snapshot sanitization, and migration replay regression tests."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.repositories.ai_event_repository import _normalize_snapshot_ref
from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.manager import AIRuntimeManager
from database import apply_migrations as apply_mig_mod
from database import provision_db as provision_mod


VALID_HIGH_ENTROPY_KEY = "A9xK2mP7qR4vW8zB3nL6tY1cF5hJ0dE2sU9wG4kM7pQ"


class TestSnapshotSanitization:
    def test_posix_absolute_path_is_sanitized(self):
        raw = "/tmp/pytest-of-root/snapshots/CAM-01_snake_1761500000_200.jpg"
        assert CameraPipeline.normalize_snapshot_ref(raw) == "/api/v1/ai/snapshots/CAM-01_snake_1761500000_200.jpg"
        assert _normalize_snapshot_ref(raw) == "/api/v1/ai/snapshots/CAM-01_snake_1761500000_200.jpg"

    def test_windows_absolute_path_is_sanitized(self):
        raw = r"C:\Users\admin\secret_farm\cam1_rat.jpg"
        assert CameraPipeline.normalize_snapshot_ref(raw) == "/api/v1/ai/snapshots/cam1_rat.jpg"
        assert _normalize_snapshot_ref(raw) == "/api/v1/ai/snapshots/cam1_rat.jpg"

    def test_public_snapshot_url_and_http_url_preserved(self):
        pub = "/api/v1/ai/snapshots/CAM-01_rat.jpg"
        assert CameraPipeline.normalize_snapshot_ref(pub) == pub
        assert CameraPipeline.normalize_snapshot_ref("https://cdn.example/img.jpg") == "https://cdn.example/img.jpg"

    def test_dot_traversal_returns_none(self):
        assert CameraPipeline.normalize_snapshot_ref("..") is None
        assert CameraPipeline.normalize_snapshot_ref("/var/tmp/..") is None
        assert CameraPipeline.normalize_snapshot_ref("") is None


class TestCameraWriteAuthorization:
    def test_camera_write_endpoints_fail_closed_when_auth_enabled_and_key_missing(self, monkeypatch):
        monkeypatch.setattr(settings, "ai_camera_control_require_auth", True)
        monkeypatch.setattr(settings, "ai_internal_service_key", "")
        app = create_app(runtime_manager=AIRuntimeManager(), load_configured_cameras=False)
        with TestClient(app) as client:
            for endpoint in [
                "/api/v1/ai/cameras/CAM-01/start",
                "/api/v1/ai/cameras/CAM-01/stop",
                "/api/v1/ai/cameras/CAM-01/counts/reset",
            ]:
                res = client.post(endpoint)
                assert res.status_code == 503

    def test_camera_write_endpoints_reject_missing_or_wrong_key(self, monkeypatch):
        monkeypatch.setattr(settings, "ai_camera_control_require_auth", True)
        monkeypatch.setattr(settings, "ai_internal_service_key", VALID_HIGH_ENTROPY_KEY)
        app = create_app(runtime_manager=AIRuntimeManager(), load_configured_cameras=False)
        with TestClient(app) as client:
            for endpoint in [
                "/api/v1/ai/cameras/CAM-01/start",
                "/api/v1/ai/cameras/CAM-01/stop",
                "/api/v1/ai/cameras/CAM-01/counts/reset",
            ]:
                assert client.post(endpoint).status_code == 403
                assert client.post(endpoint, headers={"X-Internal-Service-Key": "wrong-key"}).status_code == 403

    def test_camera_write_endpoints_allow_valid_service_key(self, monkeypatch):
        monkeypatch.setattr(settings, "ai_camera_control_require_auth", True)
        monkeypatch.setattr(settings, "ai_internal_service_key", VALID_HIGH_ENTROPY_KEY)
        app = create_app(runtime_manager=AIRuntimeManager(), load_configured_cameras=False)
        with TestClient(app) as client:
            # Passes auth guard and reaches normal 404 for unregistered camera
            res = client.post(
                "/api/v1/ai/cameras/CAM-UNREGISTERED/stop",
                headers={"X-Internal-Service-Key": VALID_HIGH_ENTROPY_KEY},
            )
            assert res.status_code == 404


class TestMigrationSecurityAndReplay:
    def test_apply_migrations_has_no_hardcoded_password_or_cross_service_env_read(self):
        src = Path(apply_mig_mod.__file__).read_text(encoding="utf-8")
        assert "ai_dev_pass" not in src
        assert "ALTER ROLE" not in src
        assert "management-service" not in src
        assert "LEGACY_IOT_DATABASE_URL" not in src

    def test_apply_migrations_skips_already_applied_versions_on_replay(self):
        applied_versions: set[str] = set()
        executed_sql: list[str] = []

        class FakeCursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, query, params=None):
                q = str(query)
                executed_sql.append(q)
                if "INSERT INTO schema_migrations" in q and params:
                    applied_versions.add(params[0])

            def fetchall(self):
                return [(v,) for v in applied_versions]

        class FakeConn:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def cursor(self):
                return FakeCursor()

        with patch.object(apply_mig_mod.psycopg, "connect", return_value=FakeConn()):
            first = apply_mig_mod.apply_migrations("postgresql://ai_user:secret@localhost:5432/ai_db")
            second = apply_mig_mod.apply_migrations("postgresql://ai_user:secret@localhost:5432/ai_db")

        assert len(first) >= 1
        assert second == []

    def test_provision_db_rejects_missing_or_short_password(self):
        with pytest.raises(ValueError):
            provision_mod.provision_ai_database("", "StrongPass_2026!")
        with pytest.raises(ValueError):
            provision_mod.provision_ai_database("postgresql://admin@localhost/postgres", "short")
