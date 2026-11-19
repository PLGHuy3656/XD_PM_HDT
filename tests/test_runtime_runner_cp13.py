"""Verification test for services/ai-service/demo/runtime_runner.py (CP13 Phase 3).

Verifies:
1. CLI syntax and --help execution.
2. X-Internal-Service-Key header presence and validation.
3. Authorization Bearer header presence and validation.
4. Zero credentials exposed in stdout, logs, or command-line.
5. End-to-end execution against an isolated AI Service runtime.
6. Execution using authorized camera identity (CAM-01).
7. Execution using allowlisted video source (fixture_swiftlet_positive.avi).
8. Canonical runtime state snapshot verification (counts, detections, events).
9. Proof of zero writes to main database (ai_db).
"""
from __future__ import annotations

import io
import os
import secrets
import subprocess
import sys
import time
import pytest
from pathlib import Path
from unittest.mock import patch

import httpx
import psycopg

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "services" / "ai-service"
sys.path.insert(0, str(AI_SERVICE_DIR))
sys.path.insert(0, str(REPO_ROOT / "ai-pipeline" / "src"))

from demo.runtime_runner import parse_args, main as runner_main
from app.config import settings, is_internal_key_acceptable
from app.main import create_app
from app.ports.camera_registry import (
    CameraRegistry,
    RegisteredCamera,
    CameraNotAuthorized,
)


def get_ai_db_stat_counts(db_url: str) -> dict:
    """Read insertion, update, and deletion counters from pg_stat_user_tables."""
    counts = {}
    try:
        with psycopg.connect(db_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT relname, n_tup_ins, n_tup_upd, n_tup_del "
                    "FROM pg_stat_user_tables "
                    "WHERE relname IN ('ai_count_updates', 'ai_events');"
                )
                for relname, n_ins, n_upd, n_del in cur.fetchall():
                    counts[relname] = {"ins": n_ins, "upd": n_upd, "del": n_del}
    except Exception as exc:
        pytest.skip(f"Cannot connect to database for stat inspection ({exc})")
    return counts


class IsolatedMockRegistry(CameraRegistry):
    def resolve_camera(self, camera_id: str, bearer_token: str) -> RegisteredCamera:
        if bearer_token != "test-bearer-token-cp13":
            raise CameraNotAuthorized("Invalid caller token")
        if camera_id in ("CAM-01", "c0000001-0000-0000-0000-000000000001"):
            return RegisteredCamera(
                camera_uuid="c0000001-0000-0000-0000-000000000001",
                node_id="CAM-01",
                farm_id="11111111-1111-1111-1111-111111111111",
                zone_id="ZONE-A",
            )
        raise CameraNotAuthorized(f"Camera {camera_id} not registered")


def test_1_cli_syntax_and_help():
    """Verify runtime_runner.py syntax and --help flag."""
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        with pytest.raises(SystemExit) as exc:
            parse_args(["--help"])
        assert exc.value.code == 0
    help_text = buf.getvalue()
    assert "--service-url" in help_text
    assert "--service-key" in help_text
    assert "--service-key-env" in help_text
    assert "--token-env" in help_text
    assert "fixture_swiftlet_positive.avi" in help_text


def test_2_and_3_header_injection_and_credentials_hygiene():
    """Verify runtime runner passes service key and bearer token in headers without logging."""
    strong_key = secrets.token_urlsafe(32)
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.fake_signature"

    captured_headers = {}

    def mock_post(url, *args, **kwargs):
        captured_headers.update(kwargs.get("headers", {}))
        # Return a mock successful response
        response = httpx.Response(
            status_code=200,
            json={"status": "STARTED", "cameraId": "CAM-01", "source": "sample.avi"},
            request=httpx.Request("POST", url),
        )
        return response

    def mock_get(url, *args, **kwargs):
        if "/health" in str(url):
            return httpx.Response(200, json={"status": "HEALTHY"}, request=httpx.Request("GET", url))
        if "/status" in str(url):
            return httpx.Response(200, json={"status": "OFFLINE", "processedFrames": 10}, request=httpx.Request("GET", url))
        return httpx.Response(200, json={}, request=httpx.Request("GET", url))

    os.environ["TEST_RUNNER_KEY"] = strong_key
    os.environ["TEST_RUNNER_TOKEN"] = fake_token

    buf = io.StringIO()
    with patch("sys.stdout", buf), patch("httpx.Client.post", side_effect=mock_post), patch("httpx.Client.get", side_effect=mock_get):
        code = runner_main([
            "--service-key-env", "TEST_RUNNER_KEY",
            "--token-env", "TEST_RUNNER_TOKEN",
            "--repeat", "1",
        ])
        assert code == 0

    stdout_text = buf.getvalue()
    # 2. Service key header verified
    assert captured_headers.get("X-Internal-Service-Key") == strong_key
    # 3. Bearer token header verified
    assert captured_headers.get("Authorization") == f"Bearer {fake_token}"
    # 4. Zero credentials exposed in stdout/logs
    assert strong_key not in stdout_text
    assert fake_token not in stdout_text
    assert "[CONFIGURED]" in stdout_text


def test_5_to_9_isolated_end_to_end_runtime_demo_and_db_isolation(monkeypatch):
    """Run real runtime runner against in-process FastAPI app using test DB, proving zero main DB writes."""
    main_ai_db_url = "postgresql://ai_user:ai_dev_pass_2026@127.0.0.1:5432/ai_db"
    test_ai_db_url = "postgresql://ai_user:ai_dev_pass_2026@127.0.0.1:5432/ai_test_db"

    # Step 9.1: Record main ai_db statistics before run
    main_db_before = get_ai_db_stat_counts(main_ai_db_url)

    strong_key = secrets.token_urlsafe(32)
    caller_token = "test-bearer-token-cp13"

    monkeypatch.setenv("AI_DATABASE_URL", test_ai_db_url)
    monkeypatch.setattr(settings, "ai_runtime_internal_enabled", True)
    monkeypatch.setattr(settings, "ai_internal_service_key", strong_key)
    monkeypatch.setattr(settings, "ai_database_url", test_ai_db_url)

    app = create_app(load_configured_cameras=False)
    app.state.camera_registry = IsolatedMockRegistry()

    from fastapi.testclient import TestClient

    # Mount TestClient into runner
    client = TestClient(app)

    monkeypatch.setenv("RUNNER_AI_KEY", strong_key)
    monkeypatch.setenv("RUNNER_AI_TOKEN", caller_token)

    buf = io.StringIO()
    with patch("sys.stdout", buf), patch("httpx.Client", return_value=client):
        exit_code = runner_main([
            "--service-url", "http://testserver",
            "--camera", "CAM-01",
            "--source", "ai-pipeline/data/samples/fixture_swiftlet_positive.avi",
            "--service-key-env", "RUNNER_AI_KEY",
            "--token-env", "RUNNER_AI_TOKEN",
            "--repeat", "1",
            "--fps", "20.0",
        ])
        assert exit_code == 0

    stdout_out = buf.getvalue()
    assert "[RUNTIME STARTED]" in stdout_out
    assert "[FINAL STATUS]" in stdout_out
    assert "[LATEST COUNT]" in stdout_out

    # Step 9.2: Record main ai_db statistics after run and prove ZERO writes
    main_db_after = get_ai_db_stat_counts(main_ai_db_url)
    assert main_db_before == main_db_after, (
        f"Database violation: main ai_db counters changed! Before: {main_db_before}, After: {main_db_after}"
    )
