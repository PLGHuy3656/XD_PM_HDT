"""Multi-object tracking (AI-FR-011): ByteTrack from ultralytics, plus a numpy-only centroid fallback."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Dict, List

import numpy as np

from .schemas import Detection


class BaseTracker:
    def update(self, detections: List[Detection], frame_shape) -> List[Detection]:
        """Return detections with track_id assigned."""
        raise NotImplementedError

    def reset(self):
        pass


class _Boxes:
    """Shim for BYTETracker.update(results): needs .conf, .xywh, .cls."""

    def __init__(self, xyxy, conf, cls):
        self.conf = np.asarray(conf, dtype=np.float32)
        self.cls = np.asarray(cls, dtype=np.float32)
        xyxy = np.asarray(xyxy, dtype=np.float32).reshape(-1, 4)
        self.xyxy = xyxy
        self.xywh = np.stack([(xyxy[:, 0] + xyxy[:, 2]) / 2, (xyxy[:, 1] + xyxy[:, 3]) / 2,
                              xyxy[:, 2] - xyxy[:, 0], xyxy[:, 3] - xyxy[:, 1]], axis=1) if len(xyxy) else np.zeros((0, 4), np.float32)

    def __len__(self):
        return len(self.conf)

    def __getitem__(self, idx):
        return _Boxes(self.xyxy[idx], self.conf[idx], self.cls[idx])


class ByteTrackTracker(BaseTracker):
    def __init__(self, frame_rate: int = 30, track_high_thresh: float = 0.35,
                 track_low_thresh: float = 0.10, new_track_thresh: float = 0.35,
                 track_buffer: int = 15, match_thresh: float = 0.8, **_):
        from ultralytics.trackers.byte_tracker import BYTETracker
        self._cls = BYTETracker
        self._args = SimpleNamespace(track_high_thresh=track_high_thresh, track_low_thresh=track_low_thresh,
                                     new_track_thresh=new_track_thresh, track_buffer=track_buffer,
                                     match_thresh=match_thresh, fuse_score=True)
        self._fps = frame_rate
        self.reset()

    def reset(self):
        try:                       # older ultralytics: BYTETracker(args, frame_rate)
            self._bt = self._cls(self._args, frame_rate=self._fps)
        except TypeError:          # newer: BYTETracker(args)
            self._bt = self._cls(self._args)

    def update(self, detections, frame_shape):
        # ByteTrack takes numbers only: map class names to temporary indexes
        idx = {n: i for i, n in enumerate(sorted({d.cls for d in detections}))}
        boxes = _Boxes([d.bbox for d in detections], [d.confidence for d in detections],
                       [idx[d.cls] for d in detections])
        out: List[Detection] = []
        for t in self._bt.update(boxes, None):       # row: x1 y1 x2 y2 id score cls det_idx
            di = int(t[7])
            if 0 <= di < len(detections):
                out.append(Detection(detections[di].cls, float(t[5]), [float(v) for v in t[:4]], int(t[4])))
        return out


class CentroidTracker(BaseTracker):
    """Minimal greedy tracker by center distance. No external dependency."""

    def __init__(self, max_distance: float = 0.15, max_missed: int = 5, **_):
        self.max_distance, self.max_missed = max_distance, max_missed
        self.reset()

    def reset(self):
        self._next = 1
        self._tracks: Dict[int, dict] = {}

    def update(self, detections, frame_shape):
        h, w = frame_shape[:2]
        maxd = self.max_distance * float(np.hypot(w, h))     # distance limit as fraction of frame diagonal
        cents = [d.center for d in detections]
        ids = list(self._tracks.keys())
        pairs = []
        for ti in ids:
            tc = self._tracks[ti]["c"]
            for di, c in enumerate(cents):
                if detections[di].cls != self._tracks[ti]["cls"]:
                    continue
                dist = float(np.hypot(tc[0] - c[0], tc[1] - c[1]))
                if dist <= maxd:
                    pairs.append((dist, ti, di))
        pairs.sort()
        used_t, used_d, assigned = set(), set(), {}
        for _, ti, di in pairs:
            if ti in used_t or di in used_d:
                continue
            used_t.add(ti)
            used_d.add(di)
            assigned[di] = ti
        for di, d in enumerate(detections):
            if di not in assigned:
                assigned[di] = self._next
                self._tracks[self._next] = {"c": cents[di], "cls": d.cls, "missed": 0}
                self._next += 1
        for ti in ids:
            if ti not in used_t:
                self._tracks[ti]["missed"] += 1
        for ti in [t for t, v in self._tracks.items() if v["missed"] > self.max_missed]:
            del self._tracks[ti]
        out = []
        for di, d in enumerate(detections):
            ti = assigned[di]
            self._tracks[ti].update(c=cents[di], missed=0)
            out.append(Detection(d.cls, d.confidence, list(d.bbox), ti))
        return out


def build_tracker(cfg, logger=None) -> BaseTracker:
    kind = cfg.get("type", "bytetrack")
    params = {k: v for k, v in cfg.items() if k != "type"}
    if kind == "bytetrack":
        try:
            return ByteTrackTracker(**params)
        except Exception as e:      # ultralytics missing or API changed
            if logger:
                logger.warning("ByteTrack unavailable (%s), using CentroidTracker", e)
    return CentroidTracker(max_distance=params.get("centroid_max_distance", 0.15),
                           max_missed=params.get("centroid_max_missed", 5))