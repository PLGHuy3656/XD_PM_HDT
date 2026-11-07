"""CameraPipeline runtime adapter around TV2's AI pipeline components (CP5.2 Task 4, 7, 8, 9, 10).

Orchestrates TV2's core components without duplicating algorithm logic:
FrameSource -> BaseDetector (YoloDetector / CallableDetector) -> BaseTracker
-> LineCounter -> PredatorMonitor -> SnapshotStore -> Canonical V1 domain objects.

Does NOT know about FastAPI, WebSocket, RabbitMQ, FCM, Frontend, or long-term Analytics.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from typing import Callable, Deque, List, Optional

log = logging.getLogger("swiftletcare.ai.camera_pipeline")

from app.config import RuntimeCameraConfig
from app.runtime.sink import NullRuntimeSink, RuntimeEventSink
from app.schemas.canonical import (
    AIEvent,
    BoundingBox,
    CameraLifecycleState,
    CameraRuntimeStatus,
    CountUpdate,
    Detection,
    DetectionResult,
    FrameInfo,
    InferenceLifecycleState,
    epoch_to_iso8601_utc,
)
from swiftletcare_ai.counter import LineCounter
from swiftletcare_ai.detector import BaseDetector
from swiftletcare_ai.frame_clean import FrameCleaner
from swiftletcare_ai.postfilter import DetectionFilter
from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.schemas import Detection as TV2Detection, FramePacket
from swiftletcare_ai.snapshot import SnapshotStore, draw_detections
from swiftletcare_ai.tracker import BaseTracker
from swiftletcare_ai.video_source import FrameSource, open_source


class CameraPipeline:
    """Reusable per-camera inference and domain adaptation pipeline."""

    def __init__(
        self,
        camera_config: RuntimeCameraConfig,
        detector: BaseDetector,
        tracker: BaseTracker,
        predator_monitor: PredatorMonitor,
        snapshot_store: Optional[SnapshotStore] = None,
        sink: Optional[RuntimeEventSink] = None,
        source_factory: Optional[Callable[[RuntimeCameraConfig], FrameSource]] = None,
        min_track_hits: int = 2,
        count_report_interval_s: float = 5.0,
        degraded_fps_threshold: float = 0.0,
        model_version: str = "yolo26n-best",
        tracker_type: str = "bytetrack",
        max_fps: float = 0.0,
        frame_cleaner: Optional[FrameCleaner] = None,
        detection_filter: Optional[DetectionFilter] = None,
        max_reconnects: int = 5,
        reconnect_delay_s: float = 2.0,
        count_window_s: float = 0.0,
    ) -> None:
        self.camera_config = camera_config
        self.detector = detector
        self.tracker = tracker
        self.predator_monitor = predator_monitor
        self.snapshot_store = snapshot_store
        self.sink: RuntimeEventSink = sink or NullRuntimeSink()
        self._source_factory = source_factory
        self.min_track_hits = max(1, int(min_track_hits))
        self.count_report_interval_s = max(0.0, float(count_report_interval_s))
        self.degraded_fps_threshold = max(0.0, float(degraded_fps_threshold))
        self.model_version = model_version
        self.tracker_type = tracker_type
        self.max_fps = max_fps
        self.frame_cleaner = frame_cleaner
        self.detection_filter = detection_filter
        self.max_reconnects = max(0, int(max_reconnects))
        self.reconnect_delay_s = max(0.01, float(reconnect_delay_s))
        self.count_window_s = max(0.0, float(count_window_s))
        self._stop_event = threading.Event()
        self._count_lock = threading.Lock()

        # Runtime state
        self._source: Optional[FrameSource] = None
        self._counter: Optional[LineCounter] = None
        self._status: CameraLifecycleState = "STARTING"
        self._inference_status: InferenceLifecycleState = "STARTING"
        self._source_connected: bool = False
        self._fps: float = 0.0
        self._width: Optional[int] = None
        self._height: Optional[int] = None
        self._processed_frames: int = 0
        self._last_frame_at: Optional[str] = None
        self._last_frame_ts: Optional[float] = None
        self._error_code: Optional[str] = None
        self._error_message: Optional[str] = None

        # Counting session state
        self._window_started_at: Optional[str] = None
        self._window_start_ts: Optional[float] = None
        self._last_emitted_entry: int = 0
        self._last_emitted_exit: int = 0
        self._last_count_report_ts: Optional[float] = None
        self._emitted_count_updates: int = 0
        self._last_frame_id: int = 0

        # FPS rolling window (wall-clock or packet timestamp deltas)
        self._frame_times: Deque[float] = deque(maxlen=30)

        # Emit initial STARTING status
        self._emit_status()

    @property
    def camera_id(self) -> str:
        return self.camera_config.camera_id

    @property
    def farm_id(self) -> Optional[str]:
        return self.camera_config.farm_id

    @property
    def zone_id(self) -> Optional[str]:
        return self.camera_config.zone_id

    @property
    def status(self) -> CameraRuntimeStatus:
        return self._build_status()

    def _build_status(self, updated_at: Optional[str] = None) -> CameraRuntimeStatus:
        return CameraRuntimeStatus(
            cameraId=self.camera_id,
            farmId=self.farm_id,
            zoneId=self.zone_id,
            status=self._status,
            sourceConnected=self._source_connected,
            inferenceStatus=self._inference_status,
            fps=self._fps,
            width=self._width,
            height=self._height,
            modelVersion=self.model_version,
            trackerType=self.tracker_type,
            processedFrames=self._processed_frames,
            lastFrameAt=self._last_frame_at,
            updatedAt=updated_at or epoch_to_iso8601_utc(),
            errorCode=self._error_code,
            errorMessage=self._error_message,
        )

    def _emit_status(self, updated_at: Optional[str] = None) -> CameraRuntimeStatus:
        status_obj = self._build_status(updated_at=updated_at)
        self.sink.on_status(status_obj)
        return status_obj

    def _transition_to_error(
        self,
        error_code: str,
        error_message: str,
        source_connected: bool = False,
        updated_at: Optional[str] = None,
    ) -> CameraRuntimeStatus:
        self._status = "ERROR"
        self._inference_status = "ERROR"
        self._source_connected = source_connected
        self._error_code = error_code
        self._error_message = error_message
        return self._emit_status(updated_at=updated_at)

    def _transition_to_degraded(
        self,
        error_code: str,
        error_message: str,
        updated_at: Optional[str] = None,
    ) -> CameraRuntimeStatus:
        prev = self._status
        self._status = "DEGRADED"
        self._inference_status = "DEGRADED"
        self._error_code = error_code
        self._error_message = error_message
        if prev != "DEGRADED":
            return self._emit_status(updated_at=updated_at)
        return self._build_status(updated_at=updated_at)

    def stop(self) -> None:
        """Signal the pipeline run loop to terminate gracefully."""
        self._stop_event.set()

    def reset_stop(self) -> None:
        """Clear the stop flag prior to starting a new run."""
        self._stop_event.clear()

    def reset_counts(self) -> CountUpdate:
        """Reset virtual line counter and window start time immediately."""
        now_iso = epoch_to_iso8601_utc()
        with self._count_lock:
            self._window_started_at = now_iso
            self._window_start_ts = self._last_frame_ts or time.time()
            self._last_count_report_ts = self._window_start_ts
            if self._counter is not None:
                self._counter.reset_counts()
            self._last_emitted_entry = 0
            self._last_emitted_exit = 0

            update = CountUpdate(
                cameraId=self.camera_id,
                farmId=self.farm_id,
                zoneId=self.zone_id,
                frameId=self._last_frame_id,
                recordedAt=now_iso,
                windowStartedAt=self._window_started_at,
                entryCount=0,
                exitCount=0,
                netChange=0,
                deltaEntry=0,
                deltaExit=0,
            )
            self.sink.on_count(update)
            return update

    @property
    def is_stopping(self) -> bool:
        return self._stop_event.is_set()

    def _is_live_source(self, src: Optional[FrameSource] = None) -> bool:
        if src is not None and getattr(src, "kind", "") in ("rtsp", "mjpeg", "webcam"):
            return True
        st = str(getattr(self.camera_config, "source_type", "")).lower()
        if st in ("rtsp", "mjpeg", "webcam"):
            return True
        raw_src = getattr(self.camera_config, "source", None)
        if isinstance(raw_src, str) and raw_src.lower().startswith(("rtsp://", "rtsps://", "http://", "https://")):
            return True
        return False

    def _open_frame_source(self) -> FrameSource:
        if self._source_factory is not None:
            src = self._source_factory(self.camera_config)
        elif isinstance(self.camera_config.source, FrameSource):
            src = self.camera_config.source
        else:
            src = open_source(
                self.camera_id,
                self.camera_config.source,
                self.camera_config.source_type,
                max_fps=self.max_fps,
            )
        self._source = src
        self._source_connected = True
        return src

    def open(self) -> FrameSource:
        """Open the configured FrameSource or transition to ERROR on failure."""
        try:
            return self._open_frame_source()
        except Exception as exc:
            self._transition_to_error(
                error_code="SOURCE_OPEN_FAILED",
                error_message=str(exc),
                source_connected=False,
            )
            raise

    def _update_fps(self, pkt_timestamp: float) -> None:
        self._frame_times.append(pkt_timestamp)
        if len(self._frame_times) >= 2:
            elapsed = self._frame_times[-1] - self._frame_times[0]
            if elapsed > 1e-6:
                self._fps = round((len(self._frame_times) - 1) / elapsed, 2)
        elif self._source is not None and getattr(self._source, "fps", 0.0) > 0:
            self._fps = round(float(self._source.fps), 2)

    @staticmethod
    def normalize_snapshot_ref(raw_ref: Optional[str]) -> Optional[str]:
        """Ensure raw filesystem paths are converted to safe relative snapshot URLs."""
        if not raw_ref:
            return None
        cleaned = raw_ref.strip()
        if not cleaned:
            return None
        if cleaned.startswith(("/", "http://", "https://")):
            return cleaned
        filename = cleaned.replace("\\", "/").rsplit("/", 1)[-1]
        return f"/api/v1/ai/snapshots/{filename}"

    @staticmethod
    def adapt_detection(tv2_det: TV2Detection) -> Detection:
        """Convert a TV2 `swiftletcare_ai.schemas.Detection` into canonical V1 `Detection`."""
        return Detection(
            **{
                "class": tv2_det.cls,
                "confidence": tv2_det.confidence,
                "bbox": BoundingBox.from_xyxy(tv2_det.bbox),
                "trackId": tv2_det.track_id,
            }
        )

    def _emit_count_update(self, frame_id: int, recorded_at: str, pkt_timestamp: float) -> CountUpdate:
        assert self._counter is not None
        if self._window_started_at is None:
            self._window_started_at = recorded_at

        entry_total = int(self._counter.entry)
        exit_total = int(self._counter.exit)
        net_change = int(self._counter.net)

        delta_entry = max(0, entry_total - self._last_emitted_entry)
        delta_exit = max(0, exit_total - self._last_emitted_exit)

        self._last_emitted_entry = entry_total
        self._last_emitted_exit = exit_total
        self._last_count_report_ts = pkt_timestamp
        self._emitted_count_updates += 1

        update = CountUpdate(
            cameraId=self.camera_id,
            farmId=self.farm_id,
            zoneId=self.zone_id,
            frameId=frame_id,
            recordedAt=recorded_at,
            windowStartedAt=self._window_started_at,
            entryCount=entry_total,
            exitCount=exit_total,
            netChange=net_change,
            deltaEntry=delta_entry,
            deltaExit=delta_exit,
        )
        self.sink.on_count(update)
        return update

    def process_packet(self, pkt: FramePacket) -> Optional[DetectionResult]:
        """Process a single `FramePacket` through detect -> track -> count -> predator."""
        captured_at = epoch_to_iso8601_utc(pkt.timestamp)

        if pkt.image is None or getattr(pkt.image, "size", 0) == 0 or len(pkt.image.shape) < 2:
            self._transition_to_degraded(
                error_code="INVALID_FRAME",
                error_message=f"Frame {pkt.frame_id} is empty or malformed",
                updated_at=captured_at,
            )
            return None

        cleaned_img = pkt.image
        if self.frame_cleaner is not None:
            cleaned_img, info = self.frame_cleaner.clean(pkt.image)
            if cleaned_img is None:
                self._transition_to_degraded(
                    error_code="INVALID_FRAME",
                    error_message=f"Frame {pkt.frame_id} rejected by cleaner: {info.get('reason', 'unknown')}",
                    updated_at=captured_at,
                )
                return None

        h, w = int(cleaned_img.shape[0]), int(cleaned_img.shape[1])
        self._height, self._width = h, w
        self._last_frame_id = int(pkt.frame_id)

        with self._count_lock:
            if self._counter is None:
                self._counter = LineCounter.from_normalized(
                    self.camera_config.line,
                    cleaned_img.shape,
                    inside_side=self.camera_config.inside_side,
                    min_hits=self.min_track_hits,
                )
                self._window_started_at = captured_at
                self._window_start_ts = pkt.timestamp
            elif (
                self.count_window_s > 0.0
                and self._window_start_ts is not None
                and (pkt.timestamp - self._window_start_ts) >= self.count_window_s
            ):
                self._emit_count_update(pkt.frame_id, captured_at, pkt.timestamp)
                self._counter.reset_counts()
                self._last_emitted_entry = 0
                self._last_emitted_exit = 0
                self._window_started_at = captured_at
                self._window_start_ts = pkt.timestamp

            if self._window_start_ts is None:
                self._window_start_ts = pkt.timestamp

        # 1. Object Detection (Ultralytics preprocessing is encapsulated inside YoloDetector.detect)
        try:
            raw_detections: List[TV2Detection] = self.detector.detect(cleaned_img)
        except Exception as exc:
            self._transition_to_error(
                error_code="INFERENCE_ERROR",
                error_message=str(exc),
                source_connected=self._source_connected,
                updated_at=captured_at,
            )
            raise

        if self.detection_filter is not None:
            raw_detections = self.detection_filter.apply(raw_detections, cleaned_img.shape)

        # 2. Split swiftlets vs other classes (predators) exactly as in TV2's pipeline
        swiftlets = [d for d in raw_detections if d.cls == "swiftlet"]
        others = [d for d in raw_detections if d.cls != "swiftlet"]

        # 3. Track swiftlets
        try:
            tracked_swiftlets = self.tracker.update(swiftlets, cleaned_img.shape) if swiftlets else []
            # Keep tracker internal state advancing even on empty swiftlet frames
            if not swiftlets:
                self.tracker.update([], cleaned_img.shape)
        except Exception as exc:
            self._transition_to_error(
                error_code="TRACKER_ERROR",
                error_message=str(exc),
                source_connected=self._source_connected,
                updated_at=captured_at,
            )
            raise

        # 4. Update LineCounter
        with self._count_lock:
            crossings = self._counter.update(tracked_swiftlets, pkt.frame_id)

        # 5. Evaluate PredatorMonitor
        fired_predators = self.predator_monitor.update(others, pkt.timestamp)

        # 6. Update runtime metrics & lifecycle state (STARTING/DEGRADED -> ONLINE or ONLINE -> DEGRADED)
        self._processed_frames += 1
        self._last_frame_at = captured_at
        self._last_frame_ts = pkt.timestamp
        self._source_connected = True
        self._update_fps(pkt.timestamp)

        prev_status = self._status
        if (
            self.degraded_fps_threshold > 0.0
            and len(self._frame_times) >= 2
            and self._fps < self.degraded_fps_threshold
        ):
            self._status = "DEGRADED"
            self._inference_status = "DEGRADED"
            self._error_code = "LOW_FPS"
            self._error_message = (
                f"Effective FPS ({self._fps}) is below threshold ({self.degraded_fps_threshold})"
            )
        else:
            self._status = "ONLINE"
            self._inference_status = "RUNNING"
            self._error_code = None
            self._error_message = None

        if prev_status != self._status or self._processed_frames == 1:
            self._emit_status(updated_at=captured_at)

        # 7. Produce & emit canonical DetectionResult
        canonical_detections = [
            self.adapt_detection(d) for d in (tracked_swiftlets + others)
        ]
        det_result = DetectionResult(
            cameraId=self.camera_id,
            farmId=self.farm_id,
            zoneId=self.zone_id,
            frameId=pkt.frame_id,
            capturedAt=captured_at,
            frame=FrameInfo(width=w, height=h),
            detections=canonical_detections,
        )
        self.sink.on_detection(det_result)

        # 8. Produce & emit canonical CountUpdate when crossings occur, on initial frame, or on interval
        with self._count_lock:
            should_emit_count = (
                bool(crossings)
                or self._last_count_report_ts is None
                or (pkt.timestamp - self._last_count_report_ts) >= self.count_report_interval_s
            )
            if should_emit_count:
                self._emit_count_update(pkt.frame_id, captured_at, pkt.timestamp)

        # 9. Produce & emit canonical AIEvent for each triggered predator alert
        for pred_det in fired_predators:
            if pred_det.cls not in ("rat", "snake"):
                continue
            snapshot_ref: Optional[str] = None
            if self.snapshot_store is not None:
                try:
                    annotated = draw_detections(
                        cleaned_img,
                        tracked_swiftlets + others,
                        line=(self._counter.a, self._counter.b),
                        counts=(self._counter.entry, self._counter.exit),
                    )
                    raw_ref = self.snapshot_store.save(
                        annotated,
                        self.camera_id,
                        pred_det.cls,
                        pkt.timestamp,
                    )
                    snapshot_ref = self.normalize_snapshot_ref(raw_ref)
                except Exception as snap_exc:
                    self._transition_to_degraded(
                        error_code="SNAPSHOT_SAVE_FAILED",
                        error_message=str(snap_exc),
                        updated_at=captured_at,
                    )

            ai_event = AIEvent(
                **{
                    "eventId": f"evt_ai_{uuid.uuid4().hex[:12]}",
                    "eventType": "PREDATOR_DETECTED",
                    "cameraId": self.camera_id,
                    "farmId": self.farm_id,
                    "zoneId": self.zone_id,
                    "frameId": pkt.frame_id,
                    "detectedAt": captured_at,
                    "class": pred_det.cls,
                    "confidence": pred_det.confidence,
                    "bbox": BoundingBox.from_xyxy(pred_det.bbox),
                    "snapshot": snapshot_ref,
                }
            )
            self.sink.on_event(ai_event)

        return det_result

    def close(self) -> CameraRuntimeStatus:
        """Close the frame source and transition ONLINE/DEGRADED/STARTING -> OFFLINE."""
        if self._source is not None:
            try:
                self._source.close()
            except Exception:
                pass
            self._source = None

        self._source_connected = False
        if self._status != "ERROR":
            self._status = "OFFLINE"
            self._inference_status = "STOPPED"
            self._error_code = None
            self._error_message = None

        updated_at = self._last_frame_at or epoch_to_iso8601_utc()
        return self._emit_status(updated_at=updated_at)

    def run(self, max_frames: int = 0) -> CameraRuntimeStatus:
        """Process frames up to `max_frames` (0 = all), with auto-reconnect for live streams."""
        count = 0
        reconnect_attempts = 0
        is_live_cfg = self._is_live_source(None)

        try:
            while not self._stop_event.is_set():
                if self._source is None:
                    try:
                        src = self._open_frame_source()
                    except Exception as open_exc:
                        if (is_live_cfg or self._is_live_source(None)) and not self._stop_event.is_set():
                            reconnect_attempts += 1
                            if reconnect_attempts > self.max_reconnects:
                                self._transition_to_error(
                                    error_code="STREAM_LOST",
                                    error_message=f"Exceeded {self.max_reconnects} reconnect retries: {open_exc}",
                                    source_connected=False,
                                )
                                break
                            self._transition_to_degraded(
                                error_code="STREAM_RECONNECTING",
                                error_message=f"Open failed, reconnect attempt {reconnect_attempts}/{self.max_reconnects}: {open_exc}",
                            )
                            delay = min(30.0, self.reconnect_delay_s * (2 ** (reconnect_attempts - 1)))
                            if self._stop_event.wait(delay):
                                break
                            continue
                        else:
                            self._transition_to_error(
                                error_code="SOURCE_OPEN_FAILED",
                                error_message=str(open_exc),
                                source_connected=False,
                            )
                            raise
                else:
                    src = self._source

                is_live = self._is_live_source(src)

                try:
                    for pkt in src:
                        if self._stop_event.is_set():
                            break
                        self.process_packet(pkt)
                        count += 1
                        reconnect_attempts = 0
                        if max_frames > 0 and count >= max_frames:
                            break
                except Exception as stream_exc:
                    if self._stop_event.is_set():
                        break
                    if is_live:
                        log.warning("Stream error on camera %s: %s", self.camera_id, stream_exc)
                    else:
                        if self._status != "ERROR":
                            self._transition_to_error(
                                error_code="PIPELINE_RUNTIME_ERROR",
                                error_message=str(stream_exc),
                                source_connected=False,
                            )
                        raise

                if self._stop_event.is_set():
                    break
                if max_frames > 0 and count >= max_frames:
                    break

                if not is_live:
                    break

                reconnect_attempts += 1
                if reconnect_attempts > self.max_reconnects:
                    self._transition_to_error(
                        error_code="STREAM_LOST",
                        error_message=f"Stream dropped, gave up after {self.max_reconnects} retries",
                        source_connected=False,
                    )
                    break

                self._transition_to_degraded(
                    error_code="STREAM_RECONNECTING",
                    error_message=f"Stream dropped, reconnect attempt {reconnect_attempts}/{self.max_reconnects}",
                )
                if self._source is not None:
                    try:
                        self._source.close()
                    except Exception:
                        pass
                    self._source = None
                    self._source_connected = False

                delay = min(30.0, self.reconnect_delay_s * (2 ** (reconnect_attempts - 1)))
                if self._stop_event.wait(delay):
                    break

            # Flush any un-emitted count changes before closing
            with self._count_lock:
                if (
                    self._counter is not None
                    and self._last_frame_at is not None
                    and self._last_frame_ts is not None
                    and (
                        self._counter.entry != self._last_emitted_entry
                        or self._counter.exit != self._last_emitted_exit
                    )
                ):
                    self._emit_count_update(
                        self._last_frame_id,
                        self._last_frame_at,
                        self._last_frame_ts,
                    )
        except Exception:
            raise
        finally:
            if self._source is not None:
                try:
                    self._source.close()
                except Exception:
                    pass
                self._source = None
            self._source_connected = False

        return self.close()


__all__ = ["CameraPipeline"]
