from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.schemas import Detection


def snake(conf=0.9):
    return Detection("snake", conf, [10, 10, 50, 50])


def test_requires_consecutive_frames():
    m = PredatorMonitor(min_consecutive_frames=3, cooldown_s=10)
    assert m.update([snake()], 0) == [] and m.update([snake()], 1) == []
    assert len(m.update([snake()], 2)) == 1


def test_streak_resets_on_gap():
    m = PredatorMonitor(min_consecutive_frames=3)
    m.update([snake()], 0)
    m.update([snake()], 1)
    m.update([], 2)
    assert m.update([snake()], 3) == []


def test_below_threshold_ignored():
    m = PredatorMonitor(conf_threshold={"snake": 0.6}, min_consecutive_frames=1)
    assert m.update([snake(0.4)], 0) == []


def test_cooldown():
    m = PredatorMonitor(min_consecutive_frames=1, cooldown_s=30)
    assert len(m.update([snake()], 0)) == 1
    assert m.update([snake()], 5) == []
    assert len(m.update([snake()], 31)) == 1


def test_swiftlet_never_triggers():
    m = PredatorMonitor(min_consecutive_frames=1)
    assert m.update([Detection("swiftlet", 0.99, [0, 0, 5, 5])], 0) == []


def test_picks_highest_confidence_per_class():
    m = PredatorMonitor(min_consecutive_frames=1)
    out = m.update([snake(0.6), snake(0.95)], 0)
    assert len(out) == 1 and out[0].confidence == 0.95