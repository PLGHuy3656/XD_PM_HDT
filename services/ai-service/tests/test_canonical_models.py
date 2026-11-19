"""Tests for Canonical AI V1 Domain Models (CP5.2 Task 3 & Task 11.1-11.4, 11.6)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.canonical import (
    AIEvent,
    BoundingBox,
    CameraRuntimeStatus,
    CountUpdate,
    Detection,
    DetectionResult,
    FrameInfo,
    epoch_to_iso8601_utc,
)


# ---------------------------------------------------------------------------
# 1. BoundingBox & FrameInfo validation
# ---------------------------------------------------------------------------
def test_bounding_box_valid_pixel_coordinates():
    bbox = BoundingBox(x1=210.0, y1=480.5, x2=395.0, y2=640.0)
    assert bbox.to_dict() == {
        "x1": 210.0,
        "y1": 480.5,
        "x2": 395.0,
        "y2": 640.0,
    }


def test_bounding_box_from_xyxy_clamps_negative_zero_and_rounds():
    bbox = BoundingBox.from_xyxy([100.04, 120.06, 180.44, 200.99])
    assert bbox.to_dict() == {"x1": 100.0, "y1": 120.1, "x2": 180.4, "y2": 201.0}


@pytest.mark.parametrize(
    "bad_kwargs",
    [
        {"x1": -1.0, "y1": 10.0, "x2": 20.0, "y2": 30.0},
        {"x1": 50.0, "y1": 10.0, "x2": 20.0, "y2": 30.0},  # x2 < x1
        {"x1": 10.0, "y1": 50.0, "x2": 20.0, "y2": 30.0},  # y2 < y1
        {"x1": float("nan"), "y1": 10.0, "x2": 20.0, "y2": 30.0},
        {"x1": float("inf"), "y1": 10.0, "x2": 20.0, "y2": 30.0},
    ],
)
def test_bounding_box_rejects_invalid_coordinates(bad_kwargs):
    with pytest.raises(ValidationError):
        BoundingBox(**bad_kwargs)


def test_frame_info_rejects_non_positive_dimensions():
    assert FrameInfo(width=1280, height=720).to_dict() == {"width": 1280, "height": 720}
    with pytest.raises(ValidationError):
        FrameInfo(width=0, height=720)
    with pytest.raises(ValidationError):
        FrameInfo(width=1280, height=-10)


# ---------------------------------------------------------------------------
# 2. Detection & DetectionResult validation (no bboxNormalized, no timestamp)
# ---------------------------------------------------------------------------
def test_detection_result_canonical_shape_matches_spec():
    res = DetectionResult(
        cameraId="CAM-01",
        farmId="FARM-01",
        zoneId="ZONE-A",
        frameId=1540,
        capturedAt="2026-10-26T14:40:05.120Z",
        frame=FrameInfo(width=1280, height=720),
        detections=[
            Detection(
                **{
                    "class": "swiftlet",
                    "confidence": 0.98,
                    "bbox": {"x1": 100, "y1": 120, "x2": 180, "y2": 200},
                    "trackId": 42,
                }
            )
        ],
    )
    dumped = res.to_dict()
    assert dumped == {
        "cameraId": "CAM-01",
        "farmId": "FARM-01",
        "zoneId": "ZONE-A",
        "frameId": 1540,
        "capturedAt": "2026-10-26T14:40:05.120Z",
        "frame": {"width": 1280, "height": 720},
        "detections": [
            {
                "class": "swiftlet",
                "confidence": 0.98,
                "bbox": {"x1": 100.0, "y1": 120.0, "x2": 180.0, "y2": 200.0},
                "trackId": 42,
            }
        ],
    }
    assert "timestamp" not in dumped
    assert "bboxNormalized" not in dumped["detections"][0]


def test_detection_rejects_bbox_normalized_and_invalid_confidence():
    with pytest.raises(ValidationError):
        Detection(
            **{
                "class": "swiftlet",
                "confidence": 0.9,
                "bbox": {"x1": 10, "y1": 10, "x2": 20, "y2": 20},
                "bboxNormalized": [0.1, 0.1, 0.2, 0.2],
            }
        )
    with pytest.raises(ValidationError):
        Detection(
            **{
                "class": "swiftlet",
                "confidence": 98.0,  # percentage instead of 0..1 float
                "bbox": {"x1": 10, "y1": 10, "x2": 20, "y2": 20},
            }
        )


# ---------------------------------------------------------------------------
# 3. No duplicate timestamp fields across all canonical V1 models
# ---------------------------------------------------------------------------
def test_no_duplicate_epoch_timestamp_field_allowed_in_any_v1_model():
    iso_now = epoch_to_iso8601_utc(1_761_489_605.12)
    assert iso_now.endswith("Z")

    with pytest.raises(ValidationError):
        DetectionResult(
            cameraId="CAM-01",
            frameId=1,
            capturedAt=iso_now,
            timestamp=1761489605,  # type: ignore[call-arg]
            frame={"width": 640, "height": 480},
            detections=[],
        )

    with pytest.raises(ValidationError):
        CountUpdate(
            cameraId="CAM-01",
            frameId=1,
            recordedAt=iso_now,
            windowStartedAt=iso_now,
            timestamp=1761489605,  # type: ignore[call-arg]
            entryCount=5,
            exitCount=3,
            netChange=2,
            deltaEntry=1,
            deltaExit=0,
        )

    with pytest.raises(ValidationError):
        AIEvent(
            **{
                "eventId": "evt_1",
                "eventType": "PREDATOR_DETECTED",
                "cameraId": "CAM-01",
                "frameId": 10,
                "detectedAt": iso_now,
                "timestamp": 1761489605,
                "class": "rat",
                "confidence": 0.85,
                "bbox": {"x1": 10, "y1": 10, "x2": 50, "y2": 50},
            }
        )

    with pytest.raises(ValidationError):
        CameraRuntimeStatus(
            cameraId="CAM-01",
            status="ONLINE",
            sourceConnected=True,
            inferenceStatus="RUNNING",
            fps=15.0,
            modelVersion="yolo26n-best",
            trackerType="bytetrack",
            processedFrames=10,
            updatedAt=iso_now,
            timestamp=1761489605,  # type: ignore[call-arg]
        )


def test_iso8601_requires_timezone_and_normalizes_to_utc_z():
    res = DetectionResult(
        cameraId="CAM-01",
        frameId=1,
        capturedAt="2026-10-26T21:40:05.000+07:00",
        frame={"width": 640, "height": 480},
        detections=[],
    )
    assert res.capturedAt == "2026-10-26T14:40:05.000Z"

    with pytest.raises(ValidationError):
        DetectionResult(
            cameraId="CAM-01",
            frameId=1,
            capturedAt="2026-10-26 14:40:05",  # naive timestamp without tz
            frame={"width": 640, "height": 480},
            detections=[],
        )


# ---------------------------------------------------------------------------
# 4. CountUpdate netChange semantics & no occupancy/population fields
# ---------------------------------------------------------------------------
def test_count_update_net_change_strictly_equals_entry_minus_exit():
    cu = CountUpdate(
        cameraId="CAM-01",
        farmId="FARM-01",
        zoneId="ZONE-A",
        frameId=100,
        recordedAt="2026-10-26T14:40:10.000Z",
        windowStartedAt="2026-10-26T08:00:00.000Z",
        entryCount=120,
        exitCount=135,
        netChange=-15,
        deltaEntry=2,
        deltaExit=5,
    )
    assert cu.netChange == -15
    assert "timestamp" not in cu.to_dict()

    # Inconsistent netChange must be rejected
    with pytest.raises(ValidationError):
        CountUpdate(
            cameraId="CAM-01",
            frameId=100,
            recordedAt="2026-10-26T14:40:10.000Z",
            windowStartedAt="2026-10-26T08:00:00.000Z",
            entryCount=120,
            exitCount=100,
            netChange=999,
            deltaEntry=1,
            deltaExit=0,
        )


@pytest.mark.parametrize(
    "forbidden_field",
    ["occupancy", "currentBirdCount", "totalBirdPopulation", "returnRate"],
)
def test_count_update_forbids_occupancy_and_population_fields(forbidden_field):
    assert forbidden_field not in CountUpdate.model_fields
    kwargs = {
        "cameraId": "CAM-01",
        "frameId": 10,
        "recordedAt": "2026-10-26T14:40:10.000Z",
        "windowStartedAt": "2026-10-26T08:00:00.000Z",
        "entryCount": 10,
        "exitCount": 5,
        "netChange": 5,
        "deltaEntry": 1,
        "deltaExit": 0,
        forbidden_field: 500,
    }
    with pytest.raises(ValidationError):
        CountUpdate(**kwargs)


# ---------------------------------------------------------------------------
# 5. AIEvent & CameraRuntimeStatus validation
# ---------------------------------------------------------------------------
def test_ai_event_v1_accepts_only_predator_detected_and_predator_classes():
    ev = AIEvent(
        **{
            "eventId": "evt_ai_001",
            "eventType": "PREDATOR_DETECTED",
            "cameraId": "CAM-01",
            "farmId": "FARM-01",
            "zoneId": "ZONE-A",
            "frameId": 42,
            "detectedAt": "2026-10-26T14:40:12.340Z",
            "class": "snake",
            "confidence": 0.914,
            "bbox": {"x1": 210.0, "y1": 480.5, "x2": 395.0, "y2": 640.0},
            "snapshot": "/snapshots/CAM-01_snake_1761489612340.jpg",
        }
    )
    dumped = ev.to_dict()
    assert dumped["eventType"] == "PREDATOR_DETECTED"
    assert dumped["class"] == "snake"
    assert dumped["bbox"] == {"x1": 210.0, "y1": 480.5, "x2": 395.0, "y2": 640.0}

    for invalid_type in ("FLOCK_ANOMALY", "AUDIO", "ENTRY", "EXIT"):
        with pytest.raises(ValidationError):
            AIEvent(
                **{
                    "eventId": "evt_ai_bad",
                    "eventType": invalid_type,
                    "cameraId": "CAM-01",
                    "frameId": 1,
                    "detectedAt": "2026-10-26T14:40:12.340Z",
                    "class": "rat",
                    "confidence": 0.8,
                    "bbox": {"x1": 10, "y1": 10, "x2": 50, "y2": 50},
                }
            )

    with pytest.raises(ValidationError):
        AIEvent(
            **{
                "eventId": "evt_ai_bad_cls",
                "eventType": "PREDATOR_DETECTED",
                "cameraId": "CAM-01",
                "frameId": 1,
                "detectedAt": "2026-10-26T14:40:12.340Z",
                "class": "swiftlet",  # not a predator
                "confidence": 0.8,
                "bbox": {"x1": 10, "y1": 10, "x2": 50, "y2": 50},
            }
        )
