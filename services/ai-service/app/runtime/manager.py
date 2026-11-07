"""AIRuntimeManager orchestrating one CameraPipeline per configured camera (CP5.2 Task 4, 5, 6)."""
from __future__ import annotations

from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

import numpy as np

from app.config import (
    AI_PIPELINE_DIR,
    Cfg,
    RuntimeCameraConfig,
    load_pipeline_config,
    load_runtime_cameras,
    resolve_path,
)
from app.ports.metadata_resolver import default_camera_metadata_resolver
from app.repositories import (
    AIEventRepository,
    CountUpdateRepository,
    default_ai_event_repository,
    default_count_update_repository,
)
from app.runtime.backend_sink import HttpBackendSink
from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.rabbitmq_sink import RabbitMQRuntimeSink
from app.runtime.sink import CompositeRuntimeSink, RuntimeEventSink
from app.runtime.state_store import InMemoryAIRuntimeStateStore
from app.schemas.canonical import (
    BoundingBox,
    CameraRuntimeStatus,
    CountUpdate,
    Detection,
    DetectionResult,
    FrameInfo,
    epoch_to_iso8601_utc,
)
from swiftletcare_ai.detector import BaseDetector, YoloDetector
from swiftletcare_ai.frame_clean import FrameCleaner
from swiftletcare_ai.postfilter import DetectionFilter
from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.schemas import FramePacket
from swiftletcare_ai.snapshot import SnapshotStore, draw_detections
from swiftletcare_ai.tracker import BaseTracker, ByteTrackTracker, build_tracker
from swiftletcare_ai.video_source import FrameSource, open_source


class LockedDetector(BaseDetector):
    """Thread-safe serialized wrapper around any BaseDetector instance."""

    def __init__(self, inner: BaseDetector):
        self.inner = inner
        self.names = getattr(inner, "names", {})
        self._lock = threading.Lock()

    def detect(self, image):
        with self._lock:
            return self.inner.detect(image)

    def warmup(self):
        fn = getattr(self.inner, "warmup", None)
        if fn:
            with self._lock:
                fn()


class PruningSnapshotStore(SnapshotStore):
    """SnapshotStore with automatic pruning of oldest files when file count exceeds max_files."""

    def __init__(
        self,
        directory: str | Path = "outputs/snapshots",
        public_base_url: str = "",
        jpeg_quality: int = 85,
        max_files: int = 500,
    ) -> None:
        super().__init__(str(directory), public_base_url, jpeg_quality)
        self.max_files = max(0, int(max_files))

    @classmethod
    def from_store(cls, store: SnapshotStore, max_files: int = 500) -> "PruningSnapshotStore":
        if isinstance(store, cls):
            store.max_files = max(0, int(max_files))
            return store
        return cls(
            directory=str(store.dir),
            public_base_url=store.base,
            jpeg_quality=store.q,
            max_files=max_files,
        )

    def prune(self) -> int:
        """Remove oldest files if count exceeds max_files. Returns count of deleted files."""
        if self.max_files <= 0 or not self.dir.exists():
            return 0
        extensions = {".jpg", ".jpeg", ".png", ".webp"}
        try:
            files = [p for p in self.dir.iterdir() if p.is_file() and p.suffix.lower() in extensions]
        except OSError:
            return 0
        if len(files) <= self.max_files:
            return 0
        files.sort(key=lambda p: p.stat().st_mtime)
        to_delete = files[: len(files) - self.max_files]
        deleted = 0
        for p in to_delete:
            try:
                p.unlink(missing_ok=True)
                deleted += 1
            except OSError:
                pass
        return deleted

    def save(self, image: np.ndarray, camera_id: str, event_type: str, timestamp: float) -> str:
        ref = super().save(image, camera_id, event_type, timestamp)
        self.prune()
        return ref


class PacedRepeatFrameSource(FrameSource):
    """Wraps a FrameSource to optionally repeat each frame and pace emission at target FPS."""

    def __init__(
        self,
        inner: FrameSource,
        camera_id: str,
        repeat: int = 1,
        target_fps: float = 0.0,
    ) -> None:
        self.inner = inner
        self.camera_id = camera_id
        self.repeat = max(1, int(repeat))
        self.target_fps = float(target_fps)
        self.fps = self.target_fps if self.target_fps > 0 else float(getattr(inner, "fps", 10.0))

    def __iter__(self):
        frame_idx = 0
        base_ts: Optional[float] = None
        interval = (1.0 / self.target_fps) if self.target_fps > 0 else 0.0
        last_emit = 0.0
        for pkt in self.inner:
            if base_ts is None:
                base_ts = float(pkt.timestamp)
            for _ in range(self.repeat):
                if interval > 0 and last_emit > 0:
                    wait = interval - (time.perf_counter() - last_emit)
                    if wait > 0:
                        time.sleep(wait)
                last_emit = time.perf_counter()
                ts = base_ts + (frame_idx / self.fps)
                yield FramePacket(self.camera_id, frame_idx, ts, pkt.image)
                frame_idx += 1

    def close(self) -> None:
        self.inner.close()


class AIRuntimeManager:
    """High-level runtime manager owning per-camera CameraPipeline instances and state store."""

    def __init__(
        self,
        pipeline_cfg: Optional[Dict[str, Any]] = None,
        state_store: Optional[InMemoryAIRuntimeStateStore] = None,
        sinks: Optional[Iterable[RuntimeEventSink]] = None,
        detector: Optional[BaseDetector] = None,
        detector_factory: Optional[Callable[[Cfg, Path], BaseDetector]] = None,
        tracker_factory: Optional[Callable[[Dict[str, Any]], BaseTracker]] = None,
        source_factory: Optional[Callable[[RuntimeCameraConfig], FrameSource]] = None,
        snapshot_store: Optional[SnapshotStore] = None,
        base_dir: Path = AI_PIPELINE_DIR,
        degraded_fps_threshold: float = 0.0,
        count_repository: Optional[CountUpdateRepository] = None,
        event_repository: Optional[AIEventRepository] = None,
        backend_sink: Optional[RuntimeEventSink] = None,
        rabbitmq_sink: Optional[RuntimeEventSink] = None,
    ) -> None:
        self.cfg = Cfg(pipeline_cfg or {})
        self.base_dir = Path(base_dir)
        self.state_store = state_store or InMemoryAIRuntimeStateStore(
            count_repository=count_repository or default_count_update_repository,
            event_repository=event_repository or default_ai_event_repository,
        )

        if backend_sink is not None:
            self.backend_sink: Optional[RuntimeEventSink] = backend_sink
        else:
            candidate_sink = HttpBackendSink.from_config(self.cfg)
            self.backend_sink = candidate_sink if candidate_sink.enabled else None

        if rabbitmq_sink is not None:
            self.rabbitmq_sink: Optional[RuntimeEventSink] = rabbitmq_sink
        else:
            candidate_rmq = RabbitMQRuntimeSink.from_config(self.cfg)
            self.rabbitmq_sink = candidate_rmq if candidate_rmq.enabled else None

        active_sinks: List[RuntimeEventSink] = [self.state_store, *(sinks or [])]
        if self.backend_sink is not None:
            active_sinks.append(self.backend_sink)
        if self.rabbitmq_sink is not None:
            active_sinks.append(self.rabbitmq_sink)
        self.composite_sink = CompositeRuntimeSink(active_sinks)

        self._shared_detector = detector
        self._detector_factory = detector_factory
        self._tracker_factory = tracker_factory
        self._source_factory = source_factory
        s_cfg = self.cfg.get("snapshot", {})
        snap_max_files = int(s_cfg.get("max_files", 500))
        if snapshot_store is not None:
            self._snapshot_store: Optional[SnapshotStore] = (
                snapshot_store
                if isinstance(snapshot_store, PruningSnapshotStore)
                else PruningSnapshotStore.from_store(snapshot_store, max_files=snap_max_files)
            )
        else:
            self._snapshot_store = None
        self.degraded_fps_threshold = degraded_fps_threshold
        self._pipelines: Dict[str, CameraPipeline] = {}
        self._threads: Dict[str, threading.Thread] = {}

    @classmethod
    def from_yaml(
        cls,
        pipeline_yaml: str | Path = AI_PIPELINE_DIR / "configs" / "pipeline.yaml",
        cameras_yaml: str | Path = AI_PIPELINE_DIR / "configs" / "cameras.yaml",
        base_dir: Path = AI_PIPELINE_DIR,
        state_store: Optional[InMemoryAIRuntimeStateStore] = None,
        sinks: Optional[Iterable[RuntimeEventSink]] = None,
        detector: Optional[BaseDetector] = None,
        detector_factory: Optional[Callable[[Cfg, Path], BaseDetector]] = None,
        source_factory: Optional[Callable[[RuntimeCameraConfig], FrameSource]] = None,
    ) -> "AIRuntimeManager":
        p_cfg = load_pipeline_config(pipeline_yaml)
        cameras = load_runtime_cameras(cameras_yaml)
        manager = cls(
            pipeline_cfg=p_cfg,
            state_store=state_store,
            sinks=sinks,
            detector=detector,
            detector_factory=detector_factory,
            source_factory=source_factory,
            base_dir=base_dir,
        )
        for cam in cameras:
            manager.register_camera(cam)
        return manager

    def add_sink(self, sink: RuntimeEventSink) -> None:
        self.composite_sink.add_sink(sink)

    def remove_sink(self, sink: RuntimeEventSink) -> None:
        self.composite_sink.remove_sink(sink)

    def _get_or_create_detector(self) -> BaseDetector:
        if self._shared_detector is not None:
            return self._shared_detector
        if self._detector_factory is not None:
            raw_detector = self._detector_factory(self.cfg, self.base_dir)
            self._shared_detector = (
                LockedDetector(raw_detector)
                if not isinstance(raw_detector, LockedDetector)
                else raw_detector
            )
            return self._shared_detector

        m_cfg = self.cfg.get("model", {})
        model_path = resolve_path(m_cfg.get("path", "models/best.pt"), self.base_dir)
        raw_detector = YoloDetector(
            model_path=model_path,
            imgsz=int(m_cfg.get("imgsz", 640)),
            device=str(m_cfg.get("device", "auto")),
            half=bool(m_cfg.get("half", False)),
            min_conf=float(m_cfg.get("min_conf", 0.15)),
            iou=float(m_cfg.get("iou", 0.5)),
        )
        self._shared_detector = LockedDetector(raw_detector)
        return self._shared_detector

    def _get_or_create_snapshot_store(self) -> SnapshotStore:
        if self._snapshot_store is not None:
            return self._snapshot_store
        s_cfg = self.cfg.get("snapshot", {})
        snap_dir = resolve_path(s_cfg.get("dir", "outputs/snapshots"), self.base_dir)
        max_files = int(s_cfg.get("max_files", 500))
        self._snapshot_store = PruningSnapshotStore(
            directory=snap_dir,
            public_base_url=str(s_cfg.get("public_base_url", "")),
            jpeg_quality=int(s_cfg.get("jpeg_quality", 85)),
            max_files=max_files,
        )
        return self._snapshot_store

    def _build_tracker(self) -> tuple[BaseTracker, str]:
        t_cfg = dict(self.cfg.get("tracker", {"type": "bytetrack"}))
        if self._tracker_factory is not None:
            tr = self._tracker_factory(t_cfg)
        else:
            tr = build_tracker(t_cfg)
        actual_type = "bytetrack" if isinstance(tr, ByteTrackTracker) else "centroid"
        return tr, actual_type

    def _build_predator_monitor(self) -> PredatorMonitor:
        p_cfg = dict(self.cfg.get("predator", {}))
        return PredatorMonitor(
            classes=p_cfg.get("classes", ("rat", "snake")),
            conf_threshold=p_cfg.get("conf_threshold", {"rat": 0.5, "snake": 0.5}),
            min_consecutive_frames=int(p_cfg.get("min_consecutive_frames", 3)),
            cooldown_s=float(p_cfg.get("cooldown_s", 30.0)),
        )

    def register_camera(
        self,
        camera_config: RuntimeCameraConfig,
        detector: Optional[BaseDetector] = None,
        tracker: Optional[BaseTracker] = None,
        predator_monitor: Optional[PredatorMonitor] = None,
        snapshot_store: Optional[SnapshotStore] = None,
        frame_cleaner: Optional[FrameCleaner] = None,
        detection_filter: Optional[DetectionFilter] = None,
    ) -> CameraPipeline:
        if camera_config.camera_id in self._pipelines:
            raise ValueError(f"Camera already registered: {camera_config.camera_id}")

        if camera_config.farm_id and camera_config.zone_id:
            default_camera_metadata_resolver.set_camera_metadata(
                camera_config.camera_id,
                camera_config.farm_id,
                camera_config.zone_id,
            )

        det = detector or self._get_or_create_detector()
        raw_det = getattr(det, "inner", det)

        if frame_cleaner is not None:
            cleaner = frame_cleaner
        else:
            cleaner = None
            cc = self.cfg.get("input_cleaning", {})
            if cc and cc.get("enabled", True) and isinstance(raw_det, YoloDetector):
                cleaner = FrameCleaner(
                    min_size=int(cc.get("min_size", 32)),
                    dark_threshold=float(cc.get("dark_threshold", 60.0)),
                    target_brightness=float(cc.get("target_brightness", 100.0)),
                    enhance_dark=bool(cc.get("enhance_dark", True)),
                )

        if detection_filter is not None:
            flt = detection_filter
        else:
            flt = None
            pf = self.cfg.get("postfilter", {})
            if pf and pf.get("enabled", True) and isinstance(raw_det, YoloDetector):
                flt = DetectionFilter(
                    min_area_frac=float(pf.get("min_area_frac", 0.0005)),
                    cross_class_iou=float(pf.get("cross_class_iou", 0.6)),
                )

        if tracker is not None:
            tr = tracker
            tr_type = "bytetrack" if isinstance(tr, ByteTrackTracker) else "centroid"
        else:
            tr, tr_type = self._build_tracker()

        pred = predator_monitor or self._build_predator_monitor()
        snap = snapshot_store if snapshot_store is not None else self._get_or_create_snapshot_store()

        c_cfg = dict(self.cfg.get("counting", {}))
        r_cfg = dict(self.cfg.get("runtime", {}))
        m_cfg = dict(self.cfg.get("model", {}))
        model_version = Path(str(m_cfg.get("path", "yolo26n-best.pt"))).stem

        resolved_source = camera_config.source
        if isinstance(resolved_source, str) and not resolved_source.isdigit():
            if not resolved_source.lower().startswith(("rtsp://", "http://", "https://")):
                resolved_source = resolve_path(resolved_source, self.base_dir)

        effective_cam_cfg = RuntimeCameraConfig(
            camera_id=camera_config.camera_id,
            source=resolved_source,
            source_type=camera_config.source_type,
            line=camera_config.line,
            inside_side=camera_config.inside_side,
            farm_id=camera_config.farm_id,
            zone_id=camera_config.zone_id,
            autostart=camera_config.autostart,
        )

        pipeline = CameraPipeline(
            camera_config=effective_cam_cfg,
            detector=det,
            tracker=tr,
            predator_monitor=pred,
            snapshot_store=snap,
            sink=self.composite_sink,
            source_factory=self._source_factory,
            min_track_hits=int(c_cfg.get("min_track_hits", 2)),
            count_report_interval_s=float(c_cfg.get("report_interval_s", 5.0)),
            degraded_fps_threshold=self.degraded_fps_threshold,
            model_version=model_version,
            tracker_type=tr_type,
            max_fps=float(r_cfg.get("max_fps", 0.0)),
            frame_cleaner=cleaner,
            detection_filter=flt,
            max_reconnects=int(self.cfg.get("input_cleaning", {}).get("reconnect_retries", 5)),
            reconnect_delay_s=float(self.cfg.get("input_cleaning", {}).get("reconnect_delay_s", 2.0)),
            count_window_s=float(c_cfg.get("window_s", 0.0)),
        )
        self._pipelines[camera_config.camera_id] = pipeline
        return pipeline

    @property
    def snapshot_dir(self) -> Path:
        if self._snapshot_store is not None:
            return Path(self._snapshot_store.dir)
        s_cfg = self.cfg.get("snapshot", {})
        return Path(resolve_path(s_cfg.get("dir", "outputs/snapshots"), self.base_dir))

    def get_pipeline(self, camera_id: str) -> Optional[CameraPipeline]:
        return self._pipelines.get(camera_id)

    def list_camera_ids(self) -> List[str]:
        return sorted(self._pipelines.keys())

    def close_all(self) -> None:
        """Stop all workers and close all registered camera pipelines cleanly."""
        for cid in list(self._pipelines.keys()):
            if self.is_running(cid):
                try:
                    self.stop_camera(cid)
                except Exception:
                    pass
            else:
                try:
                    self._pipelines[cid].close()
                except Exception:
                    pass
        self._threads.clear()
        if self.backend_sink is not None:
            try:
                if hasattr(self.backend_sink, "close"):
                    self.backend_sink.close()
            except Exception:
                pass
        if self.rabbitmq_sink is not None:
            try:
                if hasattr(self.rabbitmq_sink, "close"):
                    self.rabbitmq_sink.close()
            except Exception:
                pass

    def is_running(self, camera_id: str) -> bool:
        """Return True if background worker thread for camera_id is currently running."""
        t = self._threads.get(camera_id)
        return bool(t is not None and t.is_alive())

    def start_camera(self, camera_id: str, max_frames: int = 0) -> CameraRuntimeStatus:
        """Start a background worker thread for the camera pipeline."""
        pipeline = self._pipelines.get(camera_id)
        if pipeline is None:
            raise KeyError(f"Unknown camera_id: {camera_id}")
        if self.is_running(camera_id):
            return pipeline.status

        pipeline.reset_stop()
        t = threading.Thread(
            target=self.run_camera,
            args=(camera_id, max_frames),
            name=f"CameraWorker-{camera_id}",
            daemon=True,
        )
        self._threads[camera_id] = t
        t.start()
        return pipeline.status

    def stop_camera(self, camera_id: str, timeout: float = 5.0) -> CameraRuntimeStatus:
        """Stop a running camera pipeline worker and ensure OFFLINE status."""
        pipeline = self._pipelines.get(camera_id)
        if pipeline is None:
            raise KeyError(f"Unknown camera_id: {camera_id}")
        pipeline.stop()
        t = self._threads.get(camera_id)
        if t is not None and t.is_alive():
            t.join(timeout=timeout)
        self._threads.pop(camera_id, None)
        return pipeline.close()

    def reset_camera_counts(self, camera_id: str) -> CountUpdate:
        """Reset virtual line counter and window for a camera."""
        pipeline = self._pipelines.get(camera_id)
        if pipeline is None:
            raise KeyError(f"Camera '{camera_id}' is not registered.")
        return pipeline.reset_counts()

    def run_camera(self, camera_id: str, max_frames: int = 0) -> CameraRuntimeStatus:
        pipeline = self._pipelines.get(camera_id)
        if pipeline is None:
            raise KeyError(f"Unknown camera_id: {camera_id}")
        return pipeline.run(max_frames=max_frames)

    def run_all(self, max_frames: int = 0) -> Dict[str, CameraRuntimeStatus]:
        results: Dict[str, CameraRuntimeStatus] = {}
        for cid in self.list_camera_ids():
            results[cid] = self._pipelines[cid].run(max_frames=max_frames)
        return results

    def prepare_camera_source(
        self,
        camera_id: str,
        source: Any,
        source_type: str = "auto",
        model_path: Optional[str | Path] = None,
        repeat: int = 1,
        fps: float = 0.0,
        farm_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        line: tuple[tuple[float, float], tuple[float, float]] = ((0.10, 0.55), (0.90, 0.55)),
        inside_side: str = "positive",
    ) -> CameraPipeline:
        """Register or replace a camera pipeline for a real media/video/image source."""
        if self.is_running(camera_id):
            self.stop_camera(camera_id)
        else:
            existing = self._pipelines.pop(camera_id, None)
            if existing is not None:
                try:
                    existing.close()
                except Exception:
                    pass

        if isinstance(source, FrameSource):
            raw_source = source
        else:
            src_str = str(source)
            candidate = Path(src_str)
            if candidate.exists():
                resolved_src = str(candidate.resolve())
            elif not src_str.isdigit() and not src_str.lower().startswith(("rtsp://", "http://", "https://")):
                resolved_src = resolve_path(src_str, self.base_dir)
            else:
                resolved_src = src_str
            raw_source = open_source(camera_id, resolved_src, source_type=source_type, max_fps=fps)

        if repeat > 1 or fps > 0:
            effective_source: FrameSource = PacedRepeatFrameSource(
                raw_source,
                camera_id=camera_id,
                repeat=repeat,
                target_fps=fps,
            )
        else:
            effective_source = raw_source

        det: Optional[BaseDetector] = None
        if model_path is not None:
            m_cfg = self.cfg.get("model", {})
            mp = Path(str(model_path))
            resolved_model = str(mp.resolve()) if mp.exists() else resolve_path(str(model_path), self.base_dir)
            det = LockedDetector(
                YoloDetector(
                    model_path=resolved_model,
                    imgsz=int(m_cfg.get("imgsz", 640)),
                    device=str(m_cfg.get("device", "auto")),
                    half=bool(m_cfg.get("half", False)),
                    min_conf=float(m_cfg.get("min_conf", 0.15)),
                    iou=float(m_cfg.get("iou", 0.5)),
                )
            )

        cam_cfg = RuntimeCameraConfig(
            camera_id=camera_id,
            source=effective_source,
            source_type=source_type,
            line=line,
            inside_side=inside_side,
            farm_id=farm_id,
            zone_id=zone_id,
        )
        return self.register_camera(cam_cfg, detector=det)

    def run_source(
        self,
        camera_id: str,
        source: Any,
        source_type: str = "auto",
        model_path: Optional[str | Path] = None,
        repeat: int = 1,
        fps: float = 0.0,
        max_frames: int = 0,
        farm_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        line: tuple[tuple[float, float], tuple[float, float]] = ((0.10, 0.55), (0.90, 0.55)),
        inside_side: str = "positive",
    ) -> CameraRuntimeStatus:
        """Prepare and run a camera pipeline synchronously to completion."""
        self.prepare_camera_source(
            camera_id=camera_id,
            source=source,
            source_type=source_type,
            model_path=model_path,
            repeat=repeat,
            fps=fps,
            farm_id=farm_id,
            zone_id=zone_id,
            line=line,
            inside_side=inside_side,
        )
        return self.run_camera(camera_id, max_frames=max_frames)

    def start_source_in_background(
        self,
        camera_id: str,
        source: Any,
        source_type: str = "auto",
        model_path: Optional[str | Path] = None,
        repeat: int = 1,
        fps: float = 0.0,
        max_frames: int = 0,
        farm_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        line: tuple[tuple[float, float], tuple[float, float]] = ((0.10, 0.55), (0.90, 0.55)),
        inside_side: str = "positive",
    ) -> threading.Thread:
        """Prepare a camera pipeline and launch its execution on a background worker thread."""
        self.prepare_camera_source(
            camera_id=camera_id,
            source=source,
            source_type=source_type,
            model_path=model_path,
            repeat=repeat,
            fps=fps,
            farm_id=farm_id,
            zone_id=zone_id,
            line=line,
            inside_side=inside_side,
        )
        self.start_camera(camera_id, max_frames=max_frames)
        return self._threads[camera_id]

    def analyze_single_image(
        self,
        image: np.ndarray,
        camera_id: str = "CAM-01",
        annotate: bool = False,
    ) -> tuple[DetectionResult, Optional[str]]:
        """Run one-off detection on a static image without affecting tracking, counting, state store, or WebSocket."""
        if image is None or not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Invalid image array for analysis")

        h, w = int(image.shape[0]), int(image.shape[1])
        detector = self._get_or_create_detector()
        raw_detections = detector.detect(image)

        pf = self.cfg.get("postfilter", {})
        if pf and pf.get("enabled", True):
            filter_ = DetectionFilter(
                min_area_frac=float(pf.get("min_area_frac", 0.0005)),
                cross_class_iou=float(pf.get("cross_class_iou", 0.6)),
            )
            raw_detections = filter_.apply(raw_detections, image.shape)

        canonical_detections: List[Detection] = [
            Detection(
                **{
                    "class": d.cls,
                    "confidence": d.confidence,
                    "bbox": BoundingBox.from_xyxy(d.bbox),
                    "trackId": None,
                }
            )
            for d in raw_detections
        ]

        now_iso = epoch_to_iso8601_utc()
        result = DetectionResult(
            cameraId=camera_id,
            frameId=0,
            capturedAt=now_iso,
            frame=FrameInfo(width=w, height=h),
            detections=canonical_detections,
        )

        snapshot_url: Optional[str] = None
        if annotate:
            store = self._get_or_create_snapshot_store()
            annotated_img = draw_detections(
                image,
                raw_detections,
                line=None,
                counts=None,
            )
            raw_path = store.save(
                annotated_img,
                camera_id=camera_id,
                event_type="analyze",
                timestamp=time.time(),
            )
            snapshot_url = CameraPipeline.normalize_snapshot_ref(raw_path)

        return result, snapshot_url

    def prune_snapshots(self, max_files: Optional[int] = None) -> int:
        """Prune oldest snapshot files if count exceeds limit."""
        snap_store = self._snapshot_store or self._get_or_create_snapshot_store()
        if isinstance(snap_store, PruningSnapshotStore):
            if max_files is not None:
                old_max = snap_store.max_files
                snap_store.max_files = max(0, int(max_files))
                try:
                    return snap_store.prune()
                finally:
                    snap_store.max_files = old_max
            return snap_store.prune()
        target_dir = Path(snap_store.dir)
        limit = max_files if max_files is not None else int(self.cfg.get("snapshot", {}).get("max_files", 500))
        if limit <= 0 or not target_dir.exists():
            return 0
        extensions = {".jpg", ".jpeg", ".png", ".webp"}
        files = [p for p in target_dir.iterdir() if p.is_file() and p.suffix.lower() in extensions]
        if len(files) <= limit:
            return 0
        files.sort(key=lambda p: p.stat().st_mtime)
        to_delete = files[: len(files) - limit]
        deleted = 0
        for p in to_delete:
            try:
                p.unlink(missing_ok=True)
                deleted += 1
            except OSError:
                pass
        return deleted


__all__ = ["AIRuntimeManager", "LockedDetector", "PacedRepeatFrameSource", "PruningSnapshotStore"]
