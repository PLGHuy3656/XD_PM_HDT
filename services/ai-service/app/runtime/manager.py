"""AIRuntimeManager orchestrating one CameraPipeline per configured camera (CP5.2 Task 4, 5, 6)."""
from __future__ import annotations

from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

from app.config import (
    AI_PIPELINE_DIR,
    Cfg,
    RuntimeCameraConfig,
    load_pipeline_config,
    load_runtime_cameras,
    resolve_path,
)
from app.repositories import (
    AIEventRepository,
    CountUpdateRepository,
    default_ai_event_repository,
    default_count_update_repository,
)
from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.sink import CompositeRuntimeSink, RuntimeEventSink
from app.runtime.state_store import InMemoryAIRuntimeStateStore
from app.schemas.canonical import CameraRuntimeStatus
from swiftletcare_ai.detector import BaseDetector, YoloDetector
from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.schemas import FramePacket
from swiftletcare_ai.snapshot import SnapshotStore
from swiftletcare_ai.tracker import BaseTracker, ByteTrackTracker, build_tracker
from swiftletcare_ai.video_source import FrameSource, open_source


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
    ) -> None:
        self.cfg = Cfg(pipeline_cfg or {})
        self.base_dir = Path(base_dir)
        self.state_store = state_store or InMemoryAIRuntimeStateStore(
            count_repository=count_repository or default_count_update_repository,
            event_repository=event_repository or default_ai_event_repository,
        )
        self.composite_sink = CompositeRuntimeSink([self.state_store, *(sinks or [])])
        self._shared_detector = detector
        self._detector_factory = detector_factory
        self._tracker_factory = tracker_factory
        self._source_factory = source_factory
        self._snapshot_store = snapshot_store
        self.degraded_fps_threshold = degraded_fps_threshold
        self._pipelines: Dict[str, CameraPipeline] = {}

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
            self._shared_detector = self._detector_factory(self.cfg, self.base_dir)
            return self._shared_detector

        m_cfg = self.cfg.get("model", {})
        model_path = resolve_path(m_cfg.get("path", "models/best.pt"), self.base_dir)
        self._shared_detector = YoloDetector(
            model_path=model_path,
            imgsz=int(m_cfg.get("imgsz", 640)),
            device=str(m_cfg.get("device", "auto")),
            half=bool(m_cfg.get("half", False)),
            min_conf=float(m_cfg.get("min_conf", 0.15)),
            iou=float(m_cfg.get("iou", 0.5)),
        )
        return self._shared_detector

    def _get_or_create_snapshot_store(self) -> SnapshotStore:
        if self._snapshot_store is not None:
            return self._snapshot_store
        s_cfg = self.cfg.get("snapshot", {})
        snap_dir = resolve_path(s_cfg.get("dir", "outputs/snapshots"), self.base_dir)
        self._snapshot_store = SnapshotStore(
            directory=snap_dir,
            public_base_url=str(s_cfg.get("public_base_url", "")),
            jpeg_quality=int(s_cfg.get("jpeg_quality", 85)),
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
    ) -> CameraPipeline:
        if camera_config.camera_id in self._pipelines:
            raise ValueError(f"Camera already registered: {camera_config.camera_id}")

        det = detector or self._get_or_create_detector()
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
        """Close all registered camera pipelines cleanly."""
        for pipeline in self._pipelines.values():
            try:
                pipeline.close()
            except Exception:
                pass

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
        farm_id: Optional[str] = "FARM-01",
        zone_id: Optional[str] = "ZONE-A",
        line: tuple[tuple[float, float], tuple[float, float]] = ((0.10, 0.55), (0.90, 0.55)),
        inside_side: str = "positive",
    ) -> CameraPipeline:
        """Register or replace a camera pipeline for a real media/video/image source."""
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
            det = YoloDetector(
                model_path=resolved_model,
                imgsz=int(m_cfg.get("imgsz", 640)),
                device=str(m_cfg.get("device", "auto")),
                half=bool(m_cfg.get("half", False)),
                min_conf=float(m_cfg.get("min_conf", 0.15)),
                iou=float(m_cfg.get("iou", 0.5)),
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
        farm_id: Optional[str] = "FARM-01",
        zone_id: Optional[str] = "ZONE-A",
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
        farm_id: Optional[str] = "FARM-01",
        zone_id: Optional[str] = "ZONE-A",
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
        worker = threading.Thread(
            target=self.run_camera,
            kwargs={"camera_id": camera_id, "max_frames": max_frames},
            name=f"ai-runtime-{camera_id}",
            daemon=True,
        )
        worker.start()
        return worker


__all__ = ["AIRuntimeManager", "PacedRepeatFrameSource"]
