from swiftletcare_ai.postfilter import DetectionFilter
from swiftletcare_ai.schemas import Detection

SHAPE = (480, 640, 3)


def test_tiny_box_dropped():
    out = DetectionFilter().apply([Detection("swiftlet", 0.9, [10, 10, 12, 12])], SHAPE)
    assert out == []


def test_same_object_two_labels_keeps_most_confident():
    dets = [Detection("rat", 0.64, [100, 100, 300, 300]), Detection("snake", 0.55, [105, 100, 300, 305])]
    out = DetectionFilter().apply(dets, SHAPE)
    assert [d.cls for d in out] == ["rat"]


def test_different_objects_both_kept_and_class_min_conf():
    dets = [Detection("rat", 0.9, [10, 10, 100, 100]), Detection("snake", 0.9, [300, 300, 450, 420]),
            Detection("swiftlet", 0.2, [200, 200, 240, 240])]
    out = DetectionFilter(class_min_conf={"swiftlet": 0.3}).apply(dets, SHAPE)
    assert sorted(d.cls for d in out) == ["rat", "snake"]