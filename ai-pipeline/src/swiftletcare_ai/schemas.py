"""Data contract giữa AI (TV AI) và Backend. Khớp 'Sample ... Output' trong Confluence.

timestamp: epoch seconds (int). bbox: [x1, y1, x2, y2] theo pixel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

EVENT_PREDATOR = "PREDATOR_DETECTED"
EVENT_COUNT = "COUNT_REPORT"
EVENT_ANOMALY = "FLOCK_ANOMALY"

CLASS_SWIFTLET = "swiftlet"
CLASS_RAT = "rat"
CLASS_SNAKE = "snake"


@dataclass
class Detection:
    cls: str
    confidence: float
    bbox: List[float]                 # x1, y1, x2, y2
    track_id: Optional[int] = None

    @property
    def center(self):
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "class": self.cls,
            "confidence": round(float(self.confidence), 4),
            "bbox": [int(round(v)) for v in self.bbox],
        }
        if self.track_id is not None:
            d["trackId"] = int(self.track_id)
        return d


@dataclass
class FramePacket:
    camera_id: str
    frame_id: int
    timestamp: float
    image: Any                        # numpy BGR array


@dataclass
class DetectionMessage:
    camera_id: str
    timestamp: int
    detections: List[Detection] = field(default_factory=list)

    def to_dict(self):
        return {"cameraId": self.camera_id, "timestamp": self.timestamp,
                "detections": [d.to_dict() for d in self.detections]}


@dataclass
class CountMessage:
    camera_id: str
    timestamp: int
    entry_count: int
    exit_count: int

    @property
    def net_change(self) -> int:
        return self.entry_count - self.exit_count

    def to_dict(self):
        return {"cameraId": self.camera_id, "timestamp": self.timestamp,
                "entryCount": self.entry_count, "exitCount": self.exit_count,
                "netChange": self.net_change}


@dataclass
class AnomalyEvent:
    camera_id: str
    event_type: str
    cls: str
    confidence: float
    timestamp: int
    bbox: Optional[List[float]] = None
    snapshot: Optional[str] = None
    track_id: Optional[int] = None
    detail: Optional[str] = None

    def to_dict(self):
        d: Dict[str, Any] = {
            "cameraId": self.camera_id,
            "eventType": self.event_type,
            "class": self.cls,
            "confidence": round(float(self.confidence), 4),
            "timestamp": self.timestamp,
            "snapshot": self.snapshot,
        }
        if self.bbox is not None:
            d["bbox"] = [int(round(v)) for v in self.bbox]
        if self.track_id is not None:
            d["trackId"] = int(self.track_id)
        if self.detail:
            d["detail"] = self.detail
        return d