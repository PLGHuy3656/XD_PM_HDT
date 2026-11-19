"""Unit tests for metadata resolution (OOP-106) and farm_id camera filtering (OOP-81)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
import httpx

from app.config import RuntimeCameraConfig
from app.main import create_app
from app.ports.metadata_resolver import (
    CompositeCameraMetadataResolver,
    InMemoryCameraMetadataResolver,
    ManagementCameraMetadataResolver,
    StaticConfigCameraMetadataResolver,
    default_camera_metadata_resolver,
)
from app.runtime.manager import AIRuntimeManager
from swiftletcare_ai.detector import CallableDetector
from swiftletcare_ai.snapshot import SnapshotStore
from swiftletcare_ai.video_source import ListFrameSource


def test_management_metadata_resolver_ttl_cache_and_safe_failure():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if request.url.path.endswith("/CAM-01"):
            return httpx.Response(200, json={"farm_id": "FARM-10", "zone_id": "ZONE-A"})
        return httpx.Response(404, json={"detail": "not found"})

    resolver = ManagementCameraMetadataResolver(
        base_url="http://management.local:8001",
        cache_ttl_seconds=60.0,
        enabled=True,
        transport=httpx.MockTransport(handler),
    )

    assert resolver.resolve("CAM-01") == ("FARM-10", "ZONE-A")
    # Second call served from TTL cache
    assert resolver.resolve("CAM-01") == ("FARM-10", "ZONE-A")
    assert calls["count"] == 1

    # Unresolved camera returns (None, None), never fake IDs
    assert resolver.resolve("CAM-UNKNOWN") == (None, None)


def test_management_metadata_resolver_disabled_makes_no_http_calls():
    def fail_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP should not be called when disabled")

    resolver = ManagementCameraMetadataResolver(
        base_url="http://management.local:8001",
        enabled=False,
        transport=httpx.MockTransport(fail_handler),
    )
    assert resolver.resolve("CAM-01") == (None, None)


def test_composite_metadata_resolver_precedence():
    mem = InMemoryCameraMetadataResolver()
    mem.set_camera_metadata("CAM-MEM", "FARM-MEM", "ZONE-MEM")

    static = StaticConfigCameraMetadataResolver(
        env_json_provider=lambda: json.dumps({"CAM-STATIC": {"farmId": "FARM-ST", "zoneId": "ZONE-ST"}})
    )
    comp = CompositeCameraMetadataResolver(memory_resolver=mem, management_resolver=None, static_resolver=static)

    assert comp.resolve("CAM-MEM") == ("FARM-MEM", "ZONE-MEM")
    assert comp.resolve("CAM-STATIC") == ("FARM-ST", "ZONE-ST")
    assert comp.resolve("CAM-MISSING") == (None, None)


def test_list_cameras_farm_id_filter_and_diagnostic_fields(tmp_path: Path):
    manager = AIRuntimeManager(
        detector=CallableDetector(lambda img: [], names={0: "swiftlet"}),
        snapshot_store=SnapshotStore(tmp_path / "snapshots"),
    )
    manager.register_camera(
        RuntimeCameraConfig(
            camera_id="CAM-F1",
            source=ListFrameSource("CAM-F1", [], fps=10.0),
            farm_id="FARM-01",
            zone_id="ZONE-A",
        )
    )
    manager.register_camera(
        RuntimeCameraConfig(
            camera_id="CAM-F2",
            source=ListFrameSource("CAM-F2", [], fps=10.0),
            farm_id="FARM-02",
            zone_id="ZONE-B",
        )
    )
    # Camera without static farm_id, resolved via default_camera_metadata_resolver
    manager.register_camera(
        RuntimeCameraConfig(
            camera_id="CAM-RES",
            source=ListFrameSource("CAM-RES", [], fps=10.0),
        )
    )
    default_camera_metadata_resolver.set_camera_metadata("CAM-RES", "FARM-01", "ZONE-C")

    app = create_app(
        runtime_manager=manager,
        snapshot_dir=tmp_path / "snapshots",
        load_configured_cameras=False,
    )
    with TestClient(app) as client:
        # Unfiltered returns all 3
        all_resp = client.get("/api/v1/ai/cameras")
        assert all_resp.status_code == 200
        assert [c["cameraId"] for c in all_resp.json()] == ["CAM-F1", "CAM-F2", "CAM-RES"]

        # farm_id=FARM-01 returns CAM-F1 and CAM-RES with full diagnostic fields
        f1_resp = client.get("/api/v1/ai/cameras", params={"farm_id": "FARM-01"})
        assert f1_resp.status_code == 200
        f1_cams = f1_resp.json()
        assert [c["cameraId"] for c in f1_cams] == ["CAM-F1", "CAM-RES"]
        for cam in f1_cams:
            assert cam["farmId"] == "FARM-01"
            for field in ("status", "sourceConnected", "inferenceStatus", "fps", "lastFrameAt", "errorCode", "errorMessage"):
                assert field in cam

        # CamelCase alias farmId=FARM-02
        f2_resp = client.get("/api/v1/ai/cameras", params={"farmId": "FARM-02"})
        assert f2_resp.status_code == 200
        assert [c["cameraId"] for c in f2_resp.json()] == ["CAM-F2"]
