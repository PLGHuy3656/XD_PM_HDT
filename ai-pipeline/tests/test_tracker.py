import pytest

from swiftletcare_ai.schemas import Detection
from swiftletcare_ai.tracker import CentroidTracker, build_tracker

SHAPE = (480, 640, 3)


def d(x, y, cls="swiftlet"):
    return Detection(cls, 0.9, [x - 5, y - 5, x + 5, y + 5])


def test_id_persists_across_frames():
    t = CentroidTracker()
    ids = [t.update([d(100 + 8 * i, 100)], SHAPE)[0].track_id for i in range(6)]
    assert len(set(ids)) == 1


def test_two_objects_get_distinct_ids():
    out = CentroidTracker().update([d(50, 50), d(300, 300)], SHAPE)
    assert out[0].track_id != out[1].track_id


def test_lost_track_gets_new_id_after_gap():
    t = CentroidTracker(max_missed=2)
    a = t.update([d(50, 50)], SHAPE)[0].track_id
    for _ in range(4):
        t.update([], SHAPE)
    assert t.update([d(50, 50)], SHAPE)[0].track_id != a


def test_build_tracker_centroid():
    assert isinstance(build_tracker({"type": "centroid"}), CentroidTracker)


def test_bytetrack_keeps_one_id():
    try:
        from swiftletcare_ai.tracker import ByteTrackTracker
        tr = ByteTrackTracker()
    except Exception as e:
        pytest.skip(f"ByteTrack unavailable: {e}")
    ids = set()
    for i in range(10):
        ids |= {o.track_id for o in tr.update([d(100 + 6 * i, 100)], SHAPE)}
    assert len(ids) == 1