"""Entry/exit counting with a virtual line (AI-FR-012, AI-FR-013). Pure Python, no torch.

Each track remembers the side of the line it was last on. When it reaches the other side and the step
crosses the line segment, count one crossing; direction comes from the side it left. A center exactly on
the line keeps the previous side, so it is neither missed nor double counted. Using the segment (not a
per-frame sign check only) keeps fast birds and skipped frames countable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

Point = Tuple[float, float]


def _cross(a: Point, b: Point, p: Point) -> float:
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _crosses_segment(p1: Point, p2: Point, a: Point, b: Point) -> bool:
    """True if p1 and p2 are on opposite sides of line a-b and the crossing point lies within segment a-b."""
    d1, d2 = _cross(a, b, p1), _cross(a, b, p2)
    if d1 == d2 or (d1 > 0) == (d2 > 0):
        return False
    t = d1 / (d1 - d2)
    px, py = p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])
    ab = (b[0] - a[0], b[1] - a[1])
    u = ((px - a[0]) * ab[0] + (py - a[1]) * ab[1]) / (ab[0] ** 2 + ab[1] ** 2)
    return 0.0 <= u <= 1.0


@dataclass
class CrossingEvent:
    track_id: int
    direction: str            # "entry" | "exit"


class LineCounter:
    def __init__(self, start: Point, end: Point, inside_side: str = "positive", min_hits: int = 2):
        """start/end in pixels. inside_side: side of vector start->end that is INSIDE the house.

        In image coordinates (y down) a left-to-right line has its positive side below the line.
        """
        if inside_side not in ("positive", "negative"):
            raise ValueError("inside_side must be 'positive' or 'negative'")
        self.a, self.b = start, end
        self.inside_positive = inside_side == "positive"
        self.min_hits = min_hits
        self.entry = 0
        self.exit = 0
        self._pt: Dict[int, Point] = {}       # last center not on the line
        self._side: Dict[int, bool] = {}      # True = positive side
        self._hits: Dict[int, int] = {}

    @classmethod
    def from_normalized(cls, line, frame_shape, inside_side="positive", min_hits=2):
        h, w = frame_shape[:2]
        (x1, y1), (x2, y2) = line
        return cls((x1 * w, y1 * h), (x2 * w, y2 * h), inside_side, min_hits)

    def reset_counts(self):
        self.entry = self.exit = 0

    def update(self, tracked, frame_id: int = 0) -> List[CrossingEvent]:
        """tracked: detections with track_id. Return crossings found in this frame."""
        events: List[CrossingEvent] = []
        alive = set()
        for d in tracked:
            if d.track_id is None:
                continue
            tid, cur = d.track_id, d.center
            alive.add(tid)
            self._hits[tid] = self._hits.get(tid, 0) + 1
            dist = _cross(self.a, self.b, cur)
            if dist == 0:                       # on the line: keep previous side
                continue
            side = dist > 0
            prev_side, prev_pt = self._side.get(tid), self._pt.get(tid)
            self._side[tid], self._pt[tid] = side, cur
            if prev_side is None or side == prev_side or self._hits[tid] < self.min_hits:
                continue
            if _crosses_segment(prev_pt, cur, self.a, self.b):
                direction = "exit" if prev_side == self.inside_positive else "entry"
                if direction == "entry":
                    self.entry += 1
                else:
                    self.exit += 1
                events.append(CrossingEvent(tid, direction))
        self._gc(alive)
        return events

    def _gc(self, alive, limit: int = 200):
        """Drop lost tracks to avoid memory growth."""
        if len(self._pt) > limit:
            for tid in [t for t in self._pt if t not in alive][: len(self._pt) - limit]:
                self._pt.pop(tid, None)
                self._side.pop(tid, None)
                self._hits.pop(tid, None)

    @property
    def net(self) -> int:
        return self.entry - self.exit